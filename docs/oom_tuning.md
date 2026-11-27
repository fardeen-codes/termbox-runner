# Linux OOM Killer Score Adjustment & Tuning

## oom_score_adj
Values range from `-1000` (immune to OOM killer) to `1000` (first target for kernel SIGKILL termination).
```json
{
  "limits": {
    "oom_score_adj": 500
  }
}
```
