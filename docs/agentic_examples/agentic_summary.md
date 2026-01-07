# Agentic Summary (Option B Demo)

- Confidence: 1.00
- Top bottleneck: `pre_pickup_wait` (61.9% of total_time)
- Guardrails: max_actions=2, max_total_delta=2, forbidden=arrival rates/flow mix/dwell/vessel toggles/data rewrites
- Applied actions:
  - INCREASE_GATE_IN -> num_gate_in 1 -> 2
  - INCREASE_LOADERS -> num_loaders 2 -> 3
- Baseline total_time mean/p95: 88.45 / 211.65
- After total_time mean/p95: 84.34 / 176.22
- Delta total_time mean/p95: -4.10 / -35.43
