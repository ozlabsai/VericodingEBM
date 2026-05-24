#!/usr/bin/env bash
# Run a training+eval workload on an already-provisioned RunPod pod.
# Skips provisioning + dep install; assumes /workspace/repo is already a checkout.
#
# Usage:
#   scripts/run_on_existing_pod.sh <abl_name> <config> <ssh_user@host> <port> <pod_id>
# Example:
#   scripts/run_on_existing_pod.sh a2_no_listwise configs/abl_a2_no_listwise.yaml \
#     root@64.247.201.35 10442 64hbhxwwt5dmhb
#
# Outputs to artifacts/ablations/<abl_name>/{no_surgery,stripped,token_masked}.jsonl
# Auto-deletes the pod on completion (kill bills).

set -uo pipefail
ABL_NAME=$1; CFG=$2; SSH_TARGET=$3; SSH_PORT=$4; POD_ID=$5
DEST=artifacts/ablations/${ABL_NAME}
LOG=runpod_existing_${ABL_NAME}.log
mkdir -p "$DEST"
SSH="ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519 -p $SSH_PORT $SSH_TARGET"
RSYNC_RSH="ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519 -p $SSH_PORT"

echo "[$(date +%H:%M:%S)] [$ABL_NAME] pushing config + latest code to pod ..." | tee -a "$LOG"
# rsync repo (skipping checkpoints + heavy artifacts, including the real-bug records)
rsync -avz --no-owner --no-group --delete-after \
  --exclude .venv --exclude .git --exclude wandb --exclude runs \
  --exclude data/cache --exclude __pycache__ --exclude '*.pyc' \
  --exclude .pytest_cache --exclude .ruff_cache --exclude checkpoints \
  --exclude artifacts/baselines --exclude artifacts/stats --exclude artifacts/transfer \
  --exclude artifacts/ochiai_baseline --exclude artifacts/sentinel_reliant \
  --exclude artifacts/ablations --exclude artifacts/training \
  --exclude demo --exclude review --exclude node_modules \
  -e "$RSYNC_RSH" \
  ./ "${SSH_TARGET}:/workspace/repo/" 2>&1 | tail -3 >> "$LOG"

# Pull config name + ckpt dir
CKPT_DIR=$(grep -E '^  dir:' "$CFG" | awk '{print $2}' | tr -d '"')
echo "[$(date +%H:%M:%S)] [$ABL_NAME] config=$CFG ckpt_dir=$CKPT_DIR" | tee -a "$LOG"

# Train + eval in one nohup chain on the pod
echo "[$(date +%H:%M:%S)] [$ABL_NAME] kicking off train+eval on pod $POD_ID ..." | tee -a "$LOG"
$SSH bash -lc "
  cd /workspace/repo
  # OOM fix from the original failure mode
  export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
  export WANDB_API_KEY=\$(grep WANDB_API_KEY .env | cut -d= -f2)
  export HUGGINGFACE_API_TOKEN=\$(grep HUGGINGFACE_API_TOKEN .env | cut -d= -f2)
  # Re-fetch data in case it's missing (idempotent)
  test -f data/raw/system_trajectory_843.jsonl || .venv/bin/python scripts/fetch_data.py --include-extras 2>&1 | tail -3
  nohup bash -c '
    .venv/bin/python scripts/train.py --config $CFG
    TRAIN_RC=\$?
    if [ \$TRAIN_RC -eq 0 ]; then
      .venv/bin/python scripts/score_external_records.py --config $CFG --ckpt-dir $CKPT_DIR/final --in artifacts/real_bugs/records.jsonl --out /workspace/repo/eval_no_surgery.jsonl 2>&1 | tail -3
      .venv/bin/python scripts/strip_fails_reeval.py    --config $CFG --ckpt-dir $CKPT_DIR/final --in artifacts/real_bugs/records.jsonl --out /workspace/repo/eval_stripped.jsonl    2>&1 | tail -3
      .venv/bin/python scripts/token_mask_reeval.py     --config $CFG --ckpt-dir $CKPT_DIR/final --in artifacts/real_bugs/records.jsonl --out /workspace/repo/eval_token_masked.jsonl 2>&1 | tail -3
    fi
    echo TRAIN_EVAL_EXIT \$TRAIN_RC
  ' > /workspace/repo/train.log 2>&1 < /dev/null &
  disown
  echo STARTED
"
echo "[$(date +%H:%M:%S)] [$ABL_NAME] running; polling every 60s ..." | tee -a "$LOG"

# Poll for the sentinel
while true; do
  sleep 60
  LAST=$($SSH 'tail -2 /workspace/repo/train.log 2>/dev/null' 2>/dev/null | tail -1)
  [ -z "$LAST" ] && { echo "[$(date +%H:%M:%S)] [$ABL_NAME] SSH down, retrying" | tee -a "$LOG"; continue; }
  echo "[$(date +%H:%M:%S)] [$ABL_NAME] $LAST" | tee -a "$LOG"
  echo "$LAST" | grep -q TRAIN_EVAL_EXIT && break
done

# Pull eval files
echo "[$(date +%H:%M:%S)] [$ABL_NAME] pulling eval JSONLs ..." | tee -a "$LOG"
for arm in no_surgery stripped token_masked; do
  rsync -avz --no-owner --no-group -e "$RSYNC_RSH" \
    "${SSH_TARGET}:/workspace/repo/eval_${arm}.jsonl" \
    "${DEST}/${arm}.jsonl" >> "$LOG" 2>&1
done
N=$(wc -l < "${DEST}/no_surgery.jsonl" 2>/dev/null || echo 0)
echo "[$(date +%H:%M:%S)] [$ABL_NAME] pulled $N records" | tee -a "$LOG"

# Kill pod
echo "[$(date +%H:%M:%S)] [$ABL_NAME] deleting pod $POD_ID" | tee -a "$LOG"
RUNPOD_API_KEY=$(grep RUNPOD_API_TOKEN .env | cut -d= -f2) runpodctl pod delete "$POD_ID" >> "$LOG" 2>&1
echo "[$(date +%H:%M:%S)] [$ABL_NAME] DONE" | tee -a "$LOG"
