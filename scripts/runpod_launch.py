"""Provision a RunPod H100, launch training, stream logs, clean up on exit.

Reads RUNPOD_API_TOKEN, WANDB_API_KEY, HUGGINGFACE_API_TOKEN from .env.

Workflow:
  1. Provision an H100 SXM 80GB pod with a PyTorch image
  2. Poll for SSH-ready
  3. rsync the repo (skipping .venv/data/wandb)
  4. SSH in, install uv + deps + fetch data + run training
  5. Stream stdout/stderr back to a local log file (wandb has its own dashboard)
  6. On exit (success, failure, KeyboardInterrupt), delete the pod

Usage:
    .venv/bin/python scripts/runpod_launch.py [--gpu H100 --max-steps N --keep-alive]

  --keep-alive: don't terminate the pod on exit (useful for debugging)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Bigger pytorch image with CUDA 12.4 — flash-attn-2 has wheels for this.
DEFAULT_IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"

GPU_MAP = {
    "H100": "NVIDIA H100 80GB HBM3",
    "A100_SXM": "NVIDIA A100-SXM4-80GB",
    "A100": "NVIDIA A100 80GB PCIe",
    "B200": "NVIDIA B200",
    "L40S": "NVIDIA L40S",
    "RTX_6000_ADA": "NVIDIA RTX 6000 Ada Generation",
    "RTX_5090": "NVIDIA GeForce RTX 5090",
}


def _load_env() -> dict[str, str]:
    env_file = REPO_ROOT / ".env"
    out = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def _runpod_api_env(token: str) -> dict[str, str]:
    env = os.environ.copy()
    env["RUNPOD_API_KEY"] = token
    return env


def _ctl(env: dict[str, str], *args: str) -> dict:
    """Call runpodctl and parse JSON output."""
    cmd = ["runpodctl", *args]
    print(f"  $ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"runpodctl failed: {result.stderr}")
    text = result.stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text}


def provision_pod(
    env: dict[str, str],
    *,
    gpu_id: str,
    image: str,
    name: str,
    cloud_type: str = "SECURE",
    disk_gb: int = 50,
    volume_gb: int = 50,
) -> dict:
    print(f"==> provisioning pod ({gpu_id}, {cloud_type}, {image}) ...")
    return _ctl(
        env,
        "pod", "create",
        "--gpu-id", gpu_id,
        "--cloud-type", cloud_type,
        "--image", image,
        "--name", name,
        "--container-disk-in-gb", str(disk_gb),
        "--volume-in-gb", str(volume_gb),
        "--ports", "22/tcp,8888/http",
        "--ssh",
    )


def provision_pod_with_fallback(
    env: dict[str, str],
    *,
    gpu_chain: list[tuple[str, str]],   # [(gpu_id, cloud_type), ...]
    image: str,
    name: str,
) -> tuple[dict, str, str]:
    """Try a chain of (gpu_id, cloud_type) options until one succeeds.

    Returns (pod_dict, gpu_id, cloud_type) of the one that worked.
    """
    last_err: Exception | None = None
    for gpu_id, cloud_type in gpu_chain:
        try:
            pod = provision_pod(
                env, gpu_id=gpu_id, image=image, name=name, cloud_type=cloud_type,
            )
            return pod, gpu_id, cloud_type
        except RuntimeError as e:
            print(f"  -> failed: {e}")
            last_err = e
            continue
    if last_err:
        raise last_err
    raise RuntimeError("no gpu options available")


def get_pod(env: dict[str, str], pod_id: str) -> dict:
    return _ctl(env, "pod", "get", pod_id)


def delete_pod(env: dict[str, str], pod_id: str) -> None:
    print(f"==> deleting pod {pod_id} ...")
    try:
        _ctl(env, "pod", "delete", pod_id)
        print("  pod deleted")
    except Exception as e:
        print(f"  WARN: pod delete failed: {e}", file=sys.stderr)


def wait_for_ssh(env: dict[str, str], pod_id: str, *, timeout: int = 600) -> dict:
    """Poll until pod is RUNNING AND ssh daemon accepts connections.

    runpodctl `pod get` exposes SSH coords at pod["ssh"]["ip"] / pod["ssh"]["port"]
    once the pod is allocated. But the sshd inside the container takes another
    30-90s after RUNNING to actually accept connections. We probe both.
    """
    import socket
    start = time.time()
    while time.time() - start < timeout:
        pod = get_pod(env, pod_id)
        status = pod.get("desiredStatus") or pod.get("currentStatus")
        ssh_info = pod.get("ssh") or {}
        ip = ssh_info.get("ip")
        port = ssh_info.get("port")

        if ip and port and status == "RUNNING":
            # Probe the SSH port at TCP level — RunPod reports RUNNING while
            # sshd is still booting inside the container.
            try:
                with socket.create_connection((ip, int(port)), timeout=5) as sock:
                    banner = sock.recv(64)
                    if banner.startswith(b"SSH-"):
                        return {"ip": ip, "port": int(port), "status": status}
            except OSError:
                pass
        time.sleep(10)
        print(f"  waiting for SSH ... (status={status}, ip={ip}, port={port})", flush=True)
    raise TimeoutError(f"pod {pod_id} did not come up within {timeout}s")


def ssh_cmd(ssh: dict, remote_cmd: str) -> list[str]:
    return [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-i", os.path.expanduser("~/.runpod/ssh/RunPod-Key-Go"),
        "-p", str(ssh["port"]),
        f"root@{ssh['ip']}",
        remote_cmd,
    ]


def rsync_repo(ssh: dict) -> None:
    print("==> ensuring rsync on pod (runpod/pytorch image doesn't ship it) ...")
    # rsync isn't preinstalled on runpod/pytorch:* images. Install before rsync.
    # apt-get is fine; no DEBIAN_FRONTEND fuss needed for a single binary.
    subprocess.run(
        ssh_cmd(ssh, "command -v rsync >/dev/null 2>&1 || apt-get update -qq && apt-get install -y -qq rsync"),
        check=True,
    )
    print("==> rsyncing repo to pod ...")
    excludes = [
        ".venv", ".git/objects/pack", "wandb", "runs", "data/raw",
        "data/cache", "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache",
        # Local ckpts can be huge; resume ckpts are uploaded via --resume-local-ckpt.
        "checkpoints",
        # Demo backend's node_modules is ~680 MB of tiny files — hangs rsync
        # over high-latency SSH for 30-60 min and is not needed on the
        # training pod. The demo is a local-only viz tool.
        "demo",
        # Most artifacts skipped (transfer datasets, baselines, etc.) but the
        # real-bug records the post-train eval reads from must come along.
        "artifacts/baselines", "artifacts/stats", "artifacts/transfer",
        "artifacts/ochiai_baseline", "artifacts/sentinel_reliant",
        "artifacts/ablations", "artifacts/training",
        # Stale per-pod logs from prior runs (kept in repo root by accident);
        # not needed remotely.
        "runpod_*.log", "runpod_existing_*.log",
    ]
    ex_args = []
    for e in excludes:
        ex_args.extend(["--exclude", e])
    # macOS's bundled openrsync doesn't support --info=progress2. Use plain
    # --progress which both openrsync and GNU rsync handle.
    # --no-owner --no-group: openrsync attempts to chown remote files and fails
    # with "Operation not permitted" on RunPod's container fs (we are root but
    # the syscall is blocked by image policy). The metadata mismatch is
    # harmless; without these flags rsync returns exit 23 even when content
    # transferred successfully, and our launcher then deletes the pod.
    cmd = [
        "rsync", "-rltvz", "--no-owner", "--no-group", "--progress",
        "-e", (
            f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-i {os.path.expanduser('~/.runpod/ssh/RunPod-Key-Go')} "
            f"-p {ssh['port']}"
        ),
        *ex_args,
        f"{REPO_ROOT}/",
        f"root@{ssh['ip']}:/workspace/repo/",
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", default="A100",
                        choices=list(GPU_MAP.keys()),
                        help="Preferred GPU class; falls back through community + alternates.")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--config", default="configs/default.yaml",
                        help="Training config path (relative to repo root). "
                             "Use configs/ablation_orm.yaml or ablation_bce.yaml for ablations.")
    parser.add_argument("--resume-local-ckpt", type=str, default=None,
                        help="Local checkpoint directory (containing adapter/ + head.pt) "
                             "to rsync up and resume training from. Passed to train.py "
                             "as --resume on the pod side.")
    parser.add_argument("--detach", action="store_true",
                        help="Provision, rsync, install, and kick off training "
                             "via nohup on the pod, then exit. Training survives "
                             "any local SSH session drops. Use this for long runs; "
                             "poll via ssh `tail /workspace/repo/train.log`. "
                             "Sets --keep-alive implicitly: pod must be deleted "
                             "manually via runpodctl pod delete <id> once training is done.")
    parser.add_argument("--embed-surgery", action="store_true",
                        help="Pass --embed-surgery to train.py: replace input-embedding "
                             "rows for FAILS/fails/FAIL with the mean of neutral comment "
                             "tokens before training starts. Used in run #9.")
    parser.add_argument("--keep-alive", action="store_true",
                        help="Don't delete the pod on exit (for debugging)")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--attach", type=str, default=None,
                        help="Attach to an EXISTING pod by id, skip provisioning. "
                             "Use after manually provisioning or when a previous "
                             "launcher invocation got stuck.")
    args = parser.parse_args()

    env_vars = _load_env()
    rp_token = env_vars.get("RUNPOD_API_TOKEN") or os.environ.get("RUNPOD_API_TOKEN")
    if not rp_token:
        print("ERROR: RUNPOD_API_TOKEN not found in .env or env", file=sys.stderr)
        return 2
    wandb_key = env_vars.get("WANDB_API_KEY", "")
    hf_token = env_vars.get("HUGGINGFACE_API_TOKEN", "")

    env = _runpod_api_env(rp_token)

    pod_id: str | None = None
    pod_deleted = False

    def cleanup(*_args) -> None:
        nonlocal pod_deleted
        if pod_id and not args.keep_alive and not pod_deleted:
            delete_pod(env, pod_id)
            pod_deleted = True

    signal.signal(signal.SIGINT, lambda *a: (cleanup(), sys.exit(130)))
    signal.signal(signal.SIGTERM, lambda *a: (cleanup(), sys.exit(143)))

    try:
        if args.attach:
            # Attach mode: skip provisioning, drive an existing pod.
            pod_id = args.attach
            print(f"==> attach mode: using existing pod {pod_id}")
            # Make absolutely sure we don't delete a pod we didn't create.
            args.keep_alive = True
        else:
            # 1. Provision. Preferred chain: A100 → L40S → RTX → H100 → others.
            # Community before secure since community is usually more available
            # and noticeably cheaper.
            preferred = GPU_MAP[args.gpu]
            fallbacks: list[tuple[str, str]] = [
                (preferred, "COMMUNITY"), (preferred, "SECURE"),
            ]
            # Fastest-first fallback: B200 > H100 > A100_SXM > A100 > others.
            for alt in ["B200", "H100", "A100_SXM", "A100", "L40S", "RTX_6000_ADA"]:
                alt_id = GPU_MAP.get(alt)
                if alt_id and alt_id != preferred:
                    fallbacks.append((alt_id, "COMMUNITY"))
                    fallbacks.append((alt_id, "SECURE"))
            pod, used_gpu, used_cloud = provision_pod_with_fallback(
                env,
                gpu_chain=fallbacks,
                image=args.image,
                name=f"ebm-verus-{int(time.time())}",
            )
            print(f"  pod provisioned on {used_gpu} ({used_cloud})")
            pod_id = pod.get("id")
            if not pod_id:
                print(f"ERROR: no pod id in response: {pod}", file=sys.stderr)
                return 3
            print(f"  pod_id: {pod_id}")

        # 2. Wait for SSH (works in both fresh and attach modes)
        ssh = wait_for_ssh(env, pod_id)
        print(f"==> pod up at {ssh['ip']}:{ssh['port']}")

        # 3. rsync
        rsync_repo(ssh)

        # 3b. Optional: rsync up a local checkpoint to resume from.
        resume_flag = ""
        if args.resume_local_ckpt:
            local_ckpt = Path(args.resume_local_ckpt).resolve()
            if not local_ckpt.is_dir():
                print(f"ERROR: --resume-local-ckpt is not a directory: {local_ckpt}", file=sys.stderr)
                return 4
            remote_ckpt = "/workspace/repo/_resume_ckpt"
            print(f"==> rsyncing resume checkpoint to pod: {local_ckpt} -> {remote_ckpt}")
            rsync_cmd = [
                "rsync", "-rltvz", "--no-owner", "--no-group", "--progress",
                "-e", (
                    f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"-i {os.path.expanduser('~/.runpod/ssh/RunPod-Key-Go')} "
                    f"-p {ssh['port']}"
                ),
                f"{local_ckpt}/",
                f"root@{ssh['ip']}:{remote_ckpt}/",
            ]
            subprocess.run(rsync_cmd, check=True)
            resume_flag = f"--resume {remote_ckpt}"

        # 4. Remote install + fetch data + train
        max_steps_flag = f"--max-steps {args.max_steps}" if args.max_steps else ""
        remote_script = f"""
set -euxo pipefail
cd /workspace/repo

# install uv if missing
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
export PATH="$HOME/.local/bin:$PATH"

# write .env so the script can pick up creds
cat > .env <<ENV
WANDB_API_KEY={wandb_key}
HUGGINGFACE_API_TOKEN={hf_token}
ENV
export WANDB_API_KEY={wandb_key}
export HUGGINGFACE_API_TOKEN={hf_token}
# Fix CUDA OOM fragmentation that killed the original A2/A3 ablation pods
# (stray 18GB process + train.py 32GB allocation = OOM on RTX 6000 Ada).
# expandable_segments lets PyTorch reclaim fragmented blocks.
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# deps
uv sync --no-install-project
uv pip install -e ".[gpu]" || uv pip install -e .  # gpu extras might fail; fall back

# fetch data (extras are needed by default.yaml + ablation configs)
.venv/bin/python scripts/fetch_data.py --include-extras

# verify -- non-fatal precheck. smoke_test_data still asserts on raw spec_id
# overlap, but the real training-time split uses normalized-text-hash; cosmetic
# overlaps are expected. Train script itself runs the authoritative leakage
# check and crashes if it's actually leaky.
.venv/bin/python -m pytest tests/ -p no:cacheprovider -q || true
.venv/bin/python scripts/smoke_test_data.py --system-traj data/raw/system_trajectory_843.jsonl --sft-safe data/raw/sft_safe_25k.json || echo "  (smoke_test_data exited non-zero; non-fatal)"

# -- branch on detach mode below
"""
        if args.detach:
            # Detached: install + fetch synchronously, then spawn nohup
            # training. SSH connection closes cleanly; pod stays alive.
            # Lock in keep_alive so our cleanup() does NOT delete the pod.
            args.keep_alive = True
            # Compose: train, then (if training succeeds) auto-run the three-way
            # real-bug eval against the saved checkpoint. All in one nohup chain
            # so we don't need to babysit the pod. ckpt_dir from the YAML
            # determines where the final ckpt lands.
            ckpt_dir = None
            try:
                import yaml as _yaml
                with open(REPO_ROOT / args.config) as _f:
                    ckpt_dir = _yaml.safe_load(_f).get("checkpoint", {}).get("dir")
            except Exception:
                pass
            # NOTE: previously had a post-train eval_block here; it had a quoting
            # bug that broke A3 ("syntax error: unexpected end of file"). Removed.
            # Eval is now driven from the local wrapper (relaunch_abl-style) which
            # SSHs into the pod after TRAIN_EVAL_EXIT shows up.
            # ":" is a bash no-op; needed so the "then" block isn't empty
            # (empty then-block is a syntax error).
            eval_block = ":"
            launch_script = remote_script + f"""
# Kick training in background, fully decoupled from SSH session.
# Eval is driven from the local wrapper after TRAIN_EVAL_EXIT is seen.
nohup bash -c '
.venv/bin/python scripts/train.py --config {args.config} {resume_flag} {max_steps_flag} {'--embed-surgery' if args.embed_surgery else ''}
TRAIN_RC=$?
if [ $TRAIN_RC -eq 0 ]; then
{eval_block}
fi
echo "TRAIN_EVAL_EXIT $TRAIN_RC"
' > /workspace/repo/train.log 2>&1 < /dev/null &
disown
sleep 3
TRAIN_PID=$!
if kill -0 $TRAIN_PID 2>/dev/null; then
    echo "TRAINING_STARTED PID=$TRAIN_PID"
else
    echo "TRAINING_FAILED_TO_START" >&2
    tail -50 /workspace/repo/train.log >&2 2>/dev/null || true
    exit 5
fi
"""
            print(f"==> [DETACH] launching training on pod (log on pod: /workspace/repo/train.log)")
            rc = subprocess.run(
                ssh_cmd(ssh, launch_script), check=False,
            ).returncode
            print(f"==> remote setup exit code: {rc}")
            if rc == 0:
                print()
                print(f"   pod: {pod_id}")
                print(f"   ssh: ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519 -p {ssh['port']} root@{ssh['ip']}")
                print(f"   tail logs: ssh ... 'tail -f /workspace/repo/train.log'")
                print(f"   stop pod when done: RUNPOD_API_KEY=$(...) runpodctl pod delete {pod_id}")
            return rc
        else:
            launch_script = remote_script + f"""
# train (foreground, attached to SSH session)
.venv/bin/python scripts/train.py --config {args.config} {resume_flag} {max_steps_flag} {'--embed-surgery' if args.embed_surgery else ''}
"""
            log_path = REPO_ROOT / f"runpod_run_{pod_id}.log"
            print(f"==> launching training on pod (log: {log_path})")
            proc = subprocess.Popen(
                ssh_cmd(ssh, launch_script),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1,
            )
            with log_path.open("w") as logf:
                for line in proc.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    logf.write(line)
            rc = proc.wait()
            print(f"==> remote process exit code: {rc}")
            return rc

    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
