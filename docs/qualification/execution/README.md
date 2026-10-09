# Qualification Execution Plan — DEMO-QUAL-01

REAL_DRAWING_QUALIFICATION_05 execution artifacts.

## Contents

| File | Purpose |
|---|---|
| `campaign_plan.json` | Frozen campaign contract: hashes, provider config, policies |
| `run_manifest.json` | All 27 baseline run records (24 AI + 3 structural probes) + 12 conditional |
| `dry_run.py` | Zero-inference dry run: validates manifests, mock-scores campaign |
| `validate_execution_plan.py` | Cross-validates all plan artifacts against frozen hashes |

## Frozen run counts

| Class | Drawings | Runs each | Total |
|---|---|---|---|
| CORE | Q01, Q02, Q05, Q06, Q07 | 3 | 15 |
| EXT-GATE | Q09, Q10 | 3 | 6 |
| EXT | Q03, Q04, Q08 | 1 | 3 |
| **Baseline AI** | | | **24** |
| Structural probes | P-VEC_Q01, P-OVER_Q10, P-DOWN | 1 | 3 |
| **Baseline total run records** | | | **27** |
| P-CROP (conditional G2) | P-CROP_Q09_c1..c4 | 3 each | 12 |

## Provider

```
PROVIDER=ollama.chat
MODEL=granite3.2-vision:2b
BASE_URL=http://127.0.0.1:11434  (loopback only)
REQUEST_TIMEOUT_SECONDS=600
TOTAL_RUN_BUDGET_SECONDS=900
MAX_ATTEMPTS=1
AUTOMATIC_RETRY_ALLOWED=NO
API_KEY_REQUIRED=NO
PAID_API_REQUIRED=NO
CLOUD_AI_REQUIRED=NO
```

## Running the dry run

```sh
python docs/qualification/execution/dry_run.py
```

Expected output ends with `ZERO_INFERENCE_DRY_RUN=PASS`.

## Running plan validation

```sh
python docs/qualification/execution/validate_execution_plan.py
```

Expected output ends with `VALIDATION PASSED`.

## Tests

```sh
python -m pytest tests/qualification -q
```

## Execution order

1. Preflight checks (no inference)
2. CORE easy: Q01 × 3, Q02 × 3
3. CORE medium/hard: Q05 × 3, Q06 × 3, Q07 × 3
4. EXT-GATE: Q09 × 3, Q10 × 3
5. EXT: Q03 × 1, Q04 × 1, Q08 × 1
6. Structural probes: P-VEC_Q01, P-OVER_Q10, P-DOWN
7. P-CROP (conditional — only if G2 precondition triggered)

## Constraints

- REAL_LOCAL_AI_CALLS_EXECUTED=0 during this task
- COMMIT_PERFORMED=NO
- PUSH_PERFORMED=NO
- PRODUCTION_CODE_CHANGED=NO
