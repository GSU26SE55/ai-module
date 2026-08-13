# Claude/Codex Review Brief - AI Module Optimization

> Purpose: This file is prepared for Claude Code and Codex to understand the current AI Module design, evaluate what is already good, identify what should be optimized, and propose concrete code-level changes for the Solar Lithium-ion Battery Maintenance Management System.

---

# 1. Project Context

## 1.1. Project Name

**Solar Lithium-ion Battery Maintenance Management System**

## 1.2. AI Module Goal

The AI Module supports predictive maintenance for lithium-ion batteries used in solar backup systems.

Current AI tasks:

```text
1. Predict SOH, State of Health, from battery sensor readings.
2. Detect abnormal battery behavior.
3. Return prediction results to backend.
4. Backend creates maintenance tickets based on prediction and severity.
5. Future layer: generate maintenance prescription using RAG + LLM.
```

## 1.3. Current Tech Stack

```text
Language: Python 3.11
ML Framework: PyTorch 2.3.1
Serving: FastAPI
SOH model: MambaSOHPredictor
Anomaly detection: IsolationForest
Dataset: NASA Ames Battery Dataset, converted from .mat to CSV
Future vector DB: ChromaDB
Future LLM: Claude API
```

---

# 2. Current System Flow

The current flow is:

```text
Lithium-ion Battery
    -> IoT Sensor
    -> BatteryService Backend
    -> POST /predict
    -> AI Module
    -> Response: SOH, classification, confidence, inference time
    -> BatteryAnomalyDetectedEvent
    -> TicketService
    -> Auto-create P1/P2/P3 ticket
    -> Notify staff/customer
```

Current `/predict` response:

```json
{
  "battery_id": "B0005",
  "soh_percent": 84.5,
  "classification": "Normal",
  "confidence": 0.82,
  "inference_ms": 87.4
}
```

This is good enough for an MVP, but not enough for a strong research-grade or maintenance-ready system.

---

# 3. Current Model Design

## 3.1. Current Prediction Input

Current input shape:

```text
(batch, 30, 3)
```

Features:

```text
voltage
current
temperature
```

Each prediction uses:

```text
30 timesteps x 3 features
```

## 3.2. Current MambaSOHPredictor

Current architecture:

```text
Input: (batch, 30, 3)
    -> Linear(3 -> 64)
    -> MambaBlock #1
    -> MambaBlock #2
    -> LayerNorm(64)
    -> Last timestep hidden state
    -> Linear(64 -> 32) + GELU + Dropout(0.2)
    -> Linear(32 -> 1)
    -> SOH prediction
```

The model is lightweight:

```text
Trainable parameters: about 66,497
Target latency: < 100ms on CPU
```

## 3.3. Current Anomaly Detection

Current anomaly detector:

```python
IsolationForest(
    contamination=0.1,
    n_estimators=100,
    random_state=42,
)
```

Current classification rule:

```text
score > -0.1              -> Normal
score > -0.3 OR SOH >= 80 -> Degrading
else                      -> Failed
```

---

# 4. What Is Good

## 4.1. Clear AI Module Boundary

The AI Module has a clear responsibility:

```text
Receive battery readings
Run prediction
Return structured output
Let backend handle tickets/events
```

This is a good separation of concerns.

## 4.2. Mamba for SOH Prediction Is Reasonable

Using Mamba for battery SOH prediction is reasonable because battery degradation is sequential and Mamba is suitable for time-series modeling.

## 4.3. FastAPI Is Suitable for Serving

FastAPI is appropriate for serving prediction endpoints because it is lightweight, easy to test, and easy to integrate with backend services.

## 4.4. Model Artifacts Are Versioned

The current design stores:

```text
scaler.pkl
soh_mamba_v1.0.pth
isolation_forest_v1.0.pkl
```

This is good because production inference should use the exact scaler and model artifacts from training.

## 4.5. Dataset Split Is Better Than Random Split

The current design avoids fully random splitting by using different battery IDs for train and test. This is better than mixing cycles from the same battery into both train and test.

---

# 5. Main Problems and Required Optimizations

## 5.1. Dataset Split Needs Improvement

Current design:

```text
Train: B0005, B0006, B0007
Validation: B0018 first 70%
Test: B0018 last 30%
```

Problem:

Validation and test both come from B0018. Model selection may be indirectly tuned on B0018, and final test may not fully represent generalization to a truly unseen battery.

Recommended MVP split:

```text
Train: B0005, B0006
Validation: B0007
Test: B0018
```

Stronger validation option:

```text
Leave-one-battery-out validation across B0005, B0006, B0007, and B0018.
```

## 5.2. Input Features Are Too Limited

Current model uses only:

```text
voltage
current
temperature
```

with a short 30-timestep window.

Problem:

SOH is a long-term degradation indicator. A short sensor window may miss cycle history, capacity trend, charge/discharge duration, energy throughput, impedance trend, and thermal history. The current NASA dataset does not contain full field telemetry such as SOC, BMS logs, PV power, inverter state, or grid state.

Available raw fields in the current NASA dataset:

```text
Voltage_measured
Current_measured
Temperature_measured
Current_load
Voltage_load
Time
Capacity
ambient_temperature
battery_id
test_id / cycle_id
Re
Rct
```

Recommended engineered features from the current dataset:

```text
cycle_id
capacity
previous_SOH_estimate
voltage_mean
voltage_min
voltage_slope
current_mean
temperature_mean
temperature_max
temperature_rise_rate
charge_duration
discharge_duration
rest_time
Ah_throughput
Wh_throughput
ambient_temperature
Re
Rct
```

Future solar backup context features, only when production telemetry is available:

```text
SOC
PV_power
load_power
grid_status
inverter_status
charge_controller_status
BMS_alarm_code
BMS_logs
cabinet_temperature
ambient_temperature
fan_status
operation_mode
```

Recommended architecture:

```text
Raw sensor window
    -> Mamba backbone
    -> Time-series representation
                                \
                                 concat -> prediction heads
                                /
Engineered/session features from NASA now, plus solar/BMS context later
    -> MLP projection
```

## 5.3. Classification Rule Needs Redesign

Current rule mixes SOH and anomaly score in a confusing way.

Recommended output separation:

```text
1. health_stage
2. anomaly_status
3. risk_level
```

Health stage from SOH:

```text
SOH >= 90%        -> Healthy
80% <= SOH < 90%  -> Degrading
70% <= SOH < 80%  -> Maintenance Required
SOH < 70%         -> Critical / EOL Risk
```

Anomaly status from IsolationForest:

```text
IF score normal     -> No anomaly
IF score suspicious -> Warning
IF score abnormal   -> Anomaly
```

Final risk matrix:

| Health stage | Anomaly status | Final risk |
| --- | --- | --- |
| Healthy | No anomaly | Normal |
| Healthy | Warning/Anomaly | Warning |
| Degrading | No anomaly | Degrading |
| Degrading | Warning/Anomaly | High |
| Maintenance Required | Any | Critical |
| Critical / EOL Risk | Any | Critical |

Recommended output:

```json
{
  "soh_percent": 78.2,
  "health_stage": "Maintenance Required",
  "anomaly_status": "Warning",
  "risk_level": "High"
}
```

## 5.4. RUL Prediction Is Missing

SOH answers how healthy the battery is now. RUL answers how long the battery can continue operating before end-of-life.

Recommended MVP:

Use a separate `RULMambaPredictor` first because it is easier to implement and debug than a multi-task model.

Recommended future model options:

```text
Option A: Multi-task model
Mamba backbone
    -> SOH regression head
    -> RUL regression head
    -> Health stage classification head

Option B: Separate models
MambaSOHPredictor
RULMambaPredictor
```

Recommended `/predict` addition:

```json
{
  "soh_percent": 78.2,
  "predicted_rul": 18,
  "rul_unit": "cycles"
}
```

## 5.5. Confidence Is Not True Prediction Uncertainty

Current `confidence` is derived from IsolationForest score. This is not true prediction confidence for SOH; it is an anomaly score.

Recommended fix:

```text
confidence -> anomaly_confidence
```

Better output:

```json
{
  "prediction_confidence": 0.84,
  "anomaly_score": -0.18,
  "anomaly_confidence": 0.72
}
```

Recommended uncertainty methods:

```text
MC Dropout
Deep ensembles
Quantile regression
Conformal prediction
Prediction interval calibration
```

Recommended MVP:

Use MC Dropout because it is relatively easy to add.

Example:

```json
{
  "soh_percent": 78.2,
  "soh_interval": [75.6, 81.0],
  "prediction_confidence": 0.84,
  "anomaly_score": -0.18,
  "anomaly_status": "Warning"
}
```

## 5.6. Prescription Layer Should Separate Maintenance RAG and Safety RAG

Current future layer only has one SOP knowledge base. Maintenance procedures and safety procedures are different knowledge types.

Recommended split:

```text
Maintenance RAG
Safety RAG
```

Maintenance RAG should include:

```text
Battery maintenance manual
BMS warning code guide
Solar inverter manual
Battery replacement criteria
Preventive maintenance SOP
Historical maintenance cases
Battery datasheet
Warranty and inspection policy
```

Safety RAG should include:

```text
Electrical safety SOP
Lockout/Tagout procedure
Battery isolation procedure
PPE checklist
Thermal runaway emergency guideline
Fire safety guideline
Human verification checklist
```

Recommended prescription flow:

```text
Structured Mamba Output
    -> Fault Statement Generation
    -> Query Builder
        -> Maintenance Query
        -> Safety Query
    -> Maintenance RAG Retrieval
    -> Safety RAG Retrieval
    -> LLM Prescription Report
    -> Safety Gate
    -> Ticket Creation
```

## 5.7. API Output Is Too Minimal for LLM/RAG

Current output:

```json
{
  "battery_id": "B0005",
  "soh_percent": 84.5,
  "classification": "Normal",
  "confidence": 0.82,
  "inference_ms": 87.4
}
```

Recommended output:

```json
{
  "battery_id": "B0005",
  "model_version": "1.1",
  "prediction": {
    "soh_percent": 78.2,
    "soh_interval": [75.6, 81.0],
    "predicted_rul": 18,
    "rul_unit": "cycles",
    "health_stage": "Maintenance Required",
    "prediction_confidence": 0.84
  },
  "anomaly": {
    "anomaly_score": -0.18,
    "anomaly_status": "Warning",
    "anomaly_confidence": 0.72
  },
  "risk": {
    "risk_level": "High",
    "priority": "P2",
    "reason": [
      "SOH below 80%",
      "Temperature trend increasing",
      "Anomaly score below warning threshold"
    ]
  },
  "evidence": {
    "voltage_behavior": "fast voltage drop",
    "temperature_trend": "increasing",
    "current_pattern": "stable discharge"
  },
  "inference_ms": 87.4
}
```

---

# 6. Small Issues to Fix in Current Documentation

## 6.1. `/health` says `lstm_loaded`

Current health response includes:

```json
{
  "lstm_loaded": true
}
```

But the model is Mamba.

Fix:

```json
{
  "mamba_loaded": true
}
```

## 6.2. NASA Dataset Description Should Be More Precise

If the project only uses B0005, B0006, B0007, and B0018, write:

```text
This project uses a subset of the NASA Ames Battery Dataset: B0005, B0006, B0007, and B0018.
```

## 6.3. Replace "Real-time SOH Prediction"

NASA dataset is cycle-based laboratory data, not real field streaming BMS data.

Use:

```text
near real-time inference on incoming sensor windows
```

or:

```text
online inference simulation using sliding windows
```

## 6.4. Latency <100ms Should Not Be Called P1 SLA

AI inference latency and maintenance SLA are different.

Use:

```text
AI inference latency target: <100ms.
P1 maintenance SLA: 4 hours.
```

---

# 7. Recommended Improved Architecture

## 7.1. Prediction Layer

```text
Sensor Window / Battery Session Data
    -> Preprocessing + Feature Extraction
    -> Mamba Backbone
        -> SOH Head
        -> RUL Head
        -> Health Stage Head
    -> Uncertainty Estimation
    -> Risk Scoring
```

Dataset-compatible target architecture for the current NASA data:

```text
Battery telemetry
Voltage / Current / Temperature / Current_load / Voltage_load / Time
Capacity / ambient_temperature / Re / Rct / battery_id / cycle_id
    -> Preprocessing
       Cleaning, feature extraction, cycle-based windowing
    -> Mamba prediction layer
       SOH / RUL / health_stage / uncertainty
    -> Query builder
       Generate maintenance and safety retrieval queries
    -> Maintenance RAG
       Battery manual, BMS guide, replacement criteria, maintenance SOP
    -> Safety RAG
       PPE checklist, LOTO, isolation, thermal runaway guideline
    -> LLM prescription layer
       Generate technician-facing maintenance report
    -> Human verification
       Maintenance engineer reviews before action
```

Production telemetry extension, only after real solar/BMS data exists:

```text
SOC / BMS logs / BMS alarm code / PV power / load power / grid status
inverter status / charge controller status / cabinet temperature / fan status
operation mode
```

## 7.2. Prescription Layer

```text
Structured Prediction Output
    -> Fault Statement Generator
    -> Maintenance Query Builder
    -> Safety Query Builder
    -> Maintenance RAG
    -> Safety RAG
    -> LLM Report Generator
    -> Safety Gate
    -> Ticket Priority Mapping
```

## 7.3. Ticket Priority Mapping

```text
Critical / Failed / thermal risk -> P1
Maintenance Required / low RUL   -> P2
Degrading / mild anomaly         -> P3
Normal                           -> No ticket
```

---

# 8. Recommended Sprint Optimization

## Sprint 2

```text
Train real Mamba SOH model.
Improve train/val/test split.
Fix /health from lstm_loaded to mamba_loaded.
Add health_stage output.
Separate anomaly_score and prediction_confidence.
```

## Sprint 3

```text
Build Maintenance RAG.
Build Safety RAG separately.
Design fixed /prescribe output schema.
Add safety gate.
```

## Sprint 4

```text
Integrate ticket priority mapping.
Add BatteryHealthRiskDetected event.
Log prediction + prescription + retrieved evidence.
```

## Sprint 5

```text
Benchmark latency.
Evaluate safety report quality.
Evaluate evidence consistency.
Evaluate hallucination risk.
Add human verification workflow.
```

---

# 9. Suggested Updated API Design

## 9.1. POST /predict

Purpose:

```text
Return numerical prediction, health stage, anomaly status, risk level, and evidence.
```

Recommended response:

```json
{
  "battery_id": "B0005",
  "model_version": "1.1",
  "prediction": {
    "soh_percent": 78.2,
    "soh_interval": [75.6, 81.0],
    "predicted_rul": 18,
    "rul_unit": "cycles",
    "health_stage": "Maintenance Required",
    "prediction_confidence": 0.84
  },
  "anomaly": {
    "anomaly_score": -0.18,
    "anomaly_status": "Warning",
    "anomaly_confidence": 0.72
  },
  "risk": {
    "risk_level": "High",
    "priority": "P2",
    "reason": [
      "SOH below 80%",
      "Temperature trend increasing",
      "Anomaly score below warning threshold"
    ]
  },
  "evidence": {
    "voltage_behavior": "fast voltage drop",
    "temperature_trend": "increasing",
    "current_pattern": "stable discharge"
  },
  "inference_ms": 87.4
}
```

## 9.2. POST /prescribe

Purpose:

```text
Generate safety-aware maintenance prescription using prediction output + Maintenance RAG + Safety RAG.
```

Recommended response:

```json
{
  "battery_id": "B0005",
  "fault_statement": "Battery B0005 shows SOH degradation and warning-level anomaly.",
  "maintenance_evidence": [
    {
      "source": "SOP-BAT-002",
      "summary": "Low SOH batteries require inspection and replacement planning."
    }
  ],
  "safety_evidence": [
    {
      "source": "SOP-SAFE-DC-001",
      "summary": "Battery cabinet must be isolated before physical inspection."
    }
  ],
  "prescription": {
    "summary": "Battery requires inspection within 24 hours.",
    "priority": "P2",
    "action": "Schedule battery inspection",
    "steps": [
      "Review BMS logs.",
      "Check cabinet temperature and ventilation.",
      "Measure terminal voltage and inspect connections.",
      "Prepare replacement planning if degradation is confirmed."
    ],
    "safety_warnings": [
      "Use insulated gloves and eye protection.",
      "Isolate DC source before physical inspection.",
      "Escalate immediately if swelling, smoke, unusual smell, or excessive heat is observed."
    ],
    "human_verification_required": true
  },
  "llm_inference_ms": 1240
}
```

---

# 10. Evaluation Plan

## 10.1. Prediction Metrics

```text
SOH MAE
SOH RMSE
SOH MAPE
RUL MAE
RUL RMSE
R2
Health stage Accuracy
Health stage Macro-F1
Inference latency
```

## 10.2. Anomaly Metrics

```text
Precision
Recall
F1-score
False positive rate
False negative rate
```

## 10.3. RAG/LLM Report Metrics

```text
Correctness
Actionability
Evidence consistency
Completeness
Safety coverage
PPE completeness
Escalation clarity
Human verification quality
```

## 10.4. Safety Metrics

```text
Safety Coverage Score
Unsafe Recommendation Rate
Evidence-grounded Safety Score
Human Verification Rate
```

---

# 11. Research Positioning

Current system is a good MVP for:

```text
Mamba-based SOH prediction + anomaly classification
```

But for research and stronger project contribution, it should become:

```text
Mamba-based prediction-to-safe-prescription framework
```

Core gap statement:

```text
Existing Mamba-based battery studies mainly focus on SOH/RUL numerical prediction. However, practical solar backup battery maintenance requires actionable and safety-aware prescription. This project addresses this gap by integrating Mamba-based prediction, Maintenance RAG, Safety RAG, and LLM-based report generation.
```

Vietnamese version:

```text
Các nghiên cứu Mamba về pin hiện tại chủ yếu tập trung vào dự đoán SOH/RUL dạng số. Tuy nhiên, bảo trì pin dự phòng năng lượng mặt trời trong thực tế cần khuyến nghị có thể hành động và có nhận thức an toàn. Dự án này giải quyết khoảng trống đó bằng cách tích hợp Mamba-based prediction, Maintenance RAG, Safety RAG và LLM-based report generation.
```

---

# 12. Final Assessment

## 12.1. Current Score

```text
MVP technical design: 8/10
Research readiness: 6.5/10
Production readiness: 5.5/10
```

## 12.2. Required Improvements

```text
1. Improve train/validation/test split.
2. Add RUL prediction.
3. Add engineered features and solar backup context.
4. Redesign classification into health_stage + anomaly_status + risk_level.
5. Separate anomaly score from prediction confidence.
6. Add uncertainty estimation.
7. Split SOP knowledge into Maintenance RAG and Safety RAG.
8. Add safety gate before ticket/action.
9. Improve API output for LLM/RAG.
10. Add human verification workflow.
```

## 12.3. Final Recommendation

The current AI Module is a strong MVP for Mamba-based SOH prediction and anomaly classification. However, to support practical solar backup battery maintenance, the next version should move beyond numerical prediction. It should include RUL prediction, uncertainty-aware risk scoring, separate Maintenance RAG and Safety RAG, and an LLM-based prescription layer that generates technician-facing reports with PPE, isolation checks, escalation rules, and human verification.

---

# 13. Prompt for Claude Code

Use this prompt when giving this file to Claude Code:

```text
You are a senior AI/backend engineer. Read this markdown file and review the current AI module architecture. Your task is to propose concrete code-level changes for the FastAPI + PyTorch project.

Focus on:
1. Improving /predict response schema.
2. Separating health_stage, anomaly_status, and risk_level.
3. Fixing confidence vs anomaly_score naming.
4. Adding RUL prediction design.
5. Adding uncertainty output design.
6. Splitting prescription into Maintenance RAG and Safety RAG.
7. Proposing folder structure and implementation tasks for Sprint 2 and Sprint 3.

Do not rewrite the whole project. Produce a step-by-step implementation plan and identify files that should be changed.
```

# 14. Prompt for Codex

Use this prompt when giving this file to Codex:

```text
You are Codex, a senior AI/backend coding agent working inside this repository. Read this markdown file, then inspect the existing FastAPI + PyTorch code before proposing or making changes.

Focus on concrete, repo-aware implementation:
1. Identify current files involved in /predict, /health, inference, model loading, training, and preprocessing.
2. Propose minimal code changes for Sprint 2:
   - /health mamba_loaded rename.
   - Structured /predict response schema.
   - health_stage, anomaly_status, risk_level helpers.
   - confidence rename to anomaly_confidence.
   - model_version in prediction response.
3. Propose design-only tasks for Sprint 3:
   - Maintenance RAG.
   - Safety RAG.
   - /prescribe schema.
   - safety gate.
4. Do not rewrite the whole project.
5. Keep changes compatible with existing tests where possible, and add focused tests for changed behavior.

Before editing, summarize the file-level plan. After editing, run the relevant tests and report any failures.
```
