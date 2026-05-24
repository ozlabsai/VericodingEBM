#!/usr/bin/env bash
# Audit #4: shallow-clone the main Verus repos, count `verus!`-containing source.
set -euo pipefail

WORK=/tmp/verus_corpus_audit
rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"

REPOS=(
  "https://github.com/verus-lang/verus.git"
  "https://github.com/verus-lang/verified-storage.git"
  "https://github.com/verus-lang/verus-tutorial.git"
)

echo "audit: Verus public corpus size"
echo "============================================================"
total_bytes=0
total_files=0
for url in "${REPOS[@]}"; do
  name=$(basename "$url" .git)
  echo
  echo "cloning $url ..."
  git clone --depth=1 "$url" "$name" 2>&1 | tail -3 || { echo "  failed to clone"; continue; }
  # files containing the verus! macro
  files=$(find "$name" -name '*.rs' -print 2>/dev/null | xargs grep -l '^[[:space:]]*verus!' 2>/dev/null || true)
  n=$(echo "$files" | grep -c . || true)
  bytes=0
  if [ -n "$files" ]; then
    bytes=$(echo "$files" | xargs wc -c 2>/dev/null | tail -1 | awk '{print $1}')
  fi
  printf "  %-30s  %5d files  %10d bytes\n" "$name" "$n" "$bytes"
  total_bytes=$((total_bytes + bytes))
  total_files=$((total_files + n))
done

echo
echo "============================================================"
printf "TOTAL: %d files, %d bytes (%.2f MB)\n" "$total_files" "$total_bytes" "$(echo "scale=2; $total_bytes/1000000" | bc)"
echo
mb=$(echo "scale=0; $total_bytes/1000000" | bc)
if [ "$mb" -lt 2 ]; then
  echo "conclusion: corpus < 2MB — SKIP CPT."
elif [ "$mb" -lt 20 ]; then
  echo "conclusion: corpus 2-20MB — SKIP unless Friday pipeline finishes by 14:00."
else
  echo "conclusion: corpus > 20MB — CPT pays off, run per PLAN §5.5."
fi
