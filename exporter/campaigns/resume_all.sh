#!/usr/bin/env bash

set -u

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)
base_url=${QSS_BASE_URL:-http://localhost:18000}

campaigns=(
  "statevector-balanced-10m.json|paper-statevector-balanced-10m"
  "aer-ideal-balanced-10m.json|paper-aer-ideal-balanced-10m"
  "preset-comparison-4m.json|paper-preset-comparison-4m"
  "aer-noisy-core-2m.json|paper-aer-noisy-core-2m"
  "aer-noisy-reduced-2m.json|paper-aer-noisy-reduced-2m"
  "seed-role-study.json|paper-seed-role-study"
  "resource-ablation.json|paper-resource-ablation"
)

cd "$repo_root" || exit 1
for campaign in "${campaigns[@]}"; do
  IFS='|' read -r manifest output_name <<< "$campaign"
  python3 -m exporter.create_benchmark \
    "$script_dir/$manifest" \
    --base-url "$base_url" \
    --output-dir "output/$output_name" || exit $?
done
