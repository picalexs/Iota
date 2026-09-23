# Paper benchmark campaigns

These manifests define the local campaigns for the paper evaluation.

Use the canonical molecule IDs in the manifests. The IDs match the current QSS
API records. Do not replace them with duplicate historical molecule records.

Each campaign uses seeds `11`, `17`, `23`, `29`, and `41`. The exporter writes
resumable checkpoints under `output/paper-*`. Run a command again after a
failure to submit only entries without a run ID.

The manifests do not target IBM Runtime. The noisy campaigns use local Aer and
exclude the large molecules from noisy Aer. Backend-derived noise reads IBM
backend properties but does not submit an IBM quantum job.

## Campaigns

| Manifest | Backend | Scope | Planned runs |
| --- | --- | --- | ---: |
| `statevector-balanced-10m.json` | statevector | 10 molecules, 6 algorithms | 300 |
| `aer-ideal-balanced-10m.json` | ideal Aer | 10 molecules, 6 algorithms | 300 |
| `preset-comparison-4m.json` | statevector | 4 molecules, 4 variants, 6 algorithms | 480 |
| `aer-noisy-core-2m.json` | custom noisy Aer | H2/LiH, 6 algorithms | 60 |
| `aer-noisy-reduced-2m.json` | custom noisy Aer | H2O/BeH2, VQE/SQD/SKQD | 30 |
| `aer-noisy-phoenix-2m.json` | Phoenix-derived noisy Aer | H2/LiH, 6 algorithms | 60 |
| `seed-role-study.json` | statevector | H2/LiH, five explicit seed-role variants | 50 |
| `resource-ablation.json` | statevector | H2/LiH/BeH2, SQD and SKQD budget variants | 90 |

The balanced four-molecule results are intentionally present in both the
10-molecule campaign and the preset comparison. The first campaign provides
the full molecule panel. The second campaign isolates preset effects in one
benchmark with distinct variant IDs.

## Submit

Run from the repository root:

```bash
python3 -m exporter.create_benchmark exporter/campaigns/statevector-balanced-10m.json \
  --base-url http://localhost:18000 \
  --output-dir output/paper-statevector-balanced-10m
```

Repeat for each manifest. Do not pass `--wait`; the API and workers keep the
runs queued or running. Use the matching `output/paper-*/submission.json` files
to resume interrupted submission. Export completed data later with
`exporter/export_benchmark.py` and create plots with
`exporter/plot_benchmark.py`.

To resume all campaigns with one command, run:

```bash
exporter/campaigns/resume_all.sh
```

Set `QSS_BASE_URL` when the API is not at `http://localhost:18000`.

For the Phoenix-derived campaign, also set `QSS_LOCAL_OPERATOR_TOKEN` before
running the script. The token is required to use the active saved IBM profile.
