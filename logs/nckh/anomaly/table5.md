# Table 5 — Anomaly detection (IsolationForest, contamination=0.1, seed 42)

Rate label: fade rate > train p90 = 0.4833 %SOH/cycle (rolling-median smoothed, central difference). EOL label: SOH < 80%.

| Label def | Split | Rule | Precision | Recall | F1 | Positive rate |
|-----------|-------|------|-----------|--------|----|---------------|
| rate | val | score<=-0.1 | 0.000 | 0.000 | 0.000 | 35.5% |
| rate | val | score<=-0.3 | 0.000 | 0.000 | 0.000 | 35.5% |
| rate | val | predict==-1 | 0.400 | 0.040 | 0.073 | 35.5% |
| rate | test | score<=-0.1 | 0.000 | 0.000 | 0.000 | 20.6% |
| rate | test | score<=-0.3 | 0.000 | 0.000 | 0.000 | 20.6% |
| rate | test | predict==-1 | 0.261 | 0.038 | 0.066 | 20.6% |
| rate | val | tuned score<=0.2134 (val-selected) | 0.357 | 0.995 | 0.525 | 35.5% |
| rate | test | tuned score<=0.2134 (val-selected) | 0.206 | 1.000 | 0.342 | 20.6% |
| eol | val | score<=-0.1 | 0.000 | 0.000 | 0.000 | 97.9% |
| eol | val | score<=-0.3 | 0.000 | 0.000 | 0.000 | 97.9% |
| eol | val | predict==-1 | 1.000 | 0.037 | 0.071 | 97.9% |
| eol | test | score<=-0.1 | 0.000 | 0.000 | 0.000 | 97.9% |
| eol | test | score<=-0.3 | 0.000 | 0.000 | 0.000 | 97.9% |
| eol | test | predict==-1 | 1.000 | 0.031 | 0.059 | 97.9% |
| eol | val | tuned score<=0.2134 (val-selected) | 0.980 | 0.991 | 0.985 | 97.9% |
| eol | test | tuned score<=0.2134 (val-selected) | 0.979 | 0.997 | 0.988 | 97.9% |

**Section 3.5 label definition (draft):** Since the NASA dataset lacks fault
annotations, we define a proxy anomaly label: a cycle is anomalous if its locally
smoothed degradation rate exceeds the 90th percentile of the training-set rate
distribution — aligned with the Isolation Forest contamination prior of 0.1.
An absolute SOH threshold (80% EOL) is reported for comparison but is degenerate
on the low-temperature val/test cells (~98% of windows below 80% SOH).

**Limitations (draft):** Both labels are proxies derived from capacity fade, not
real fault annotations; results measure separation of degradation regimes rather
than field sensor-fault detection.
