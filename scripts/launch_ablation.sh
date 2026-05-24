#!/usr/bin/env bash
# Launch one ablation: provision pod (B200→H100→A100 chain), train + auto-eval
# on the pod (via runpod_launch.py's new eval_block), pull results, kill pod.
#
# Usage: scripts/launch_ablation.sh <abl_name> <config_path>
#   e.g. scripts/launch_ablation.sh a2_no_listwise configs/abl_a2_no_listwise.yaml
#
# Designed to be run in parallel:
#   scripts/launch_ablation.sh a2 configs/abl_a2_no_listwise.yaml &
#   scripts/launch_ablation.sh a3 configs/abl_a3_no_semi_hard.yaml &
#   wait
#
# Output: artifacts/ablations/<abl_name>/{no_surgery,stripped,token_masked}.jsonl

set -uo pipefail

ABL_NAME=$1
CFG=$2
# Default GPU chain: B200 first (fastest), fall back to H100, then A100_SXM.
# Override with $ABL_GPU.
GPU=${ABL_GPU:-B200}
LOG=runpod_abl_${ABL_NAME}.log
DEST=artifacts/ablations/${ABL_NAME}

mkdir -p "$DEST"
echo "[$(date +%H:%M:%S)] [$ABL_NAME] launching on $GPU, log: $LOG" >&2

# Detach mode: training + post-train eval both kicked off in nohup on the pod.
.venv/bin/python scripts/runpod_launch.py --gpu "$GPU" --config "$CFG" --detach > "$LOG" 2>&1
LAUNCH_RC=$?
if [ $LAUNCH_RC -ne 0 ]; then
    echo "[$(date +%H:%M:%S)] [$ABL_NAME] launcher exit $LAUNCH_RC; see $LOG" >&2
    exit $LAUNCH_RC
fi

POD_ID=$(grep -oE 'pod: [a-z0-9]+' "$LOG" | head -1 | awk '{print $2}')
SSH_LINE=$(grep -E 'ssh:' "$LOG" | head -1 | sed 's/^[[:space:]]*ssh:[[:space:]]*//')
if [ -z "$POD_ID" ] || [ -z "$SSH_LINE" ]; then
    echo "[$(date +%H:%M:%S)] [$ABL_NAME] could not parse pod_id / ssh" >&2
    exit 2
fi
echo "[$(date +%H:%M:%S)] [$ABL_NAME] pod=$POD_ID ssh=$SSH_LINE" >&2

SSH_HOST=$(echo "$SSH_LINE" | grep -oE 'root@[0-9.]+' | sed 's/^root@//')
SSH_PORT=$(echo "$SSH_LINE" | grep -oE '\-p [0-9]+' | awk '{print $2}')
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=15 -i ~/.ssh/id_ed25519 -p $SSH_PORT root@$SSH_HOST"

# Poll for "TRAIN_EVAL_EXIT N" sentinel that the nohup chain writes when both
# training AND the three-arm eval finish (regardless of pass/fail).
echo "[$(date +%H:%M:%S)] [$ABL_NAME] waiting for train+eval to finish (polling every 60s)..." >&2
while true; do
    sleep 60
    OUT=$(ssh $SSH_OPTS 'tail -2 /workspace/repo/train.log 2>/dev/null' 2>/dev/null)
    if [ -z "$OUT" ]; then
        echo "[$(date +%H:%M:%S)] [$ABL_NAME] SSH unreachable, retrying..." >&2
        continue
    fi
    LAST_LINE=$(echo "$OUT" | tail -1)
    echo "[$(date +%H:%M:%S)] [$ABL_NAME] last: $LAST_LINE" >&2
    if echo "$LAST_LINE" | grep -q "TRAIN_EVAL_EXIT"; then
        TRAIN_RC=$(echo "$LAST_LINE" | awk '{print $NF}')
        echo "[$(date +%H:%M:%S)] [$ABL_NAME] sentinel seen, train_rc=$TRAIN_RC" >&2
        break
    fi
done

# Pull eval JSONLs back. The new launcher writes them to /workspace/repo/eval_*.jsonl
echo "[$(date +%H:%M:%S)] [$ABL_NAME] pulling eval JSONLs to $DEST/" >&2
for arm in no_surgery stripped token_masked; do
  rsync -avz --no-owner --no-group -e "ssh $SSH_OPTS" \
    "root@$SSH_HOST:/workspace/repo/eval_${arm}.jsonl" \
    "$DEST/${arm}.jsonl" >> "$LOG" 2>&1
done

# Sanity check + kill pod (always kill, even on training failure, to stop billing)
N_LINES=$(wc -l < "$DEST/no_surgery.jsonl" 2>/dev/null || echo 0)
echo "[$(date +%H:%M:%S)] [$ABL_NAME] pulled $N_LINES no-surgery records" >&2

echo "[$(date +%H:%M:%S)] [$ABL_NAME] deleting pod $POD_ID" >&2
RUNPOD_API_KEY=$(grep RUNPOD_API_TOKEN .env | cut -d= -f2) runpodctl pod delete "$POD_ID" >> "$LOG" 2>&1

echo "[$(date +%H:%M:%S)] [$ABL_NAME] DONE. results: $DEST/" >&2
