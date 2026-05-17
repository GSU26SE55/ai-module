def classify_anomaly(score: float, soh: float) -> str:
    """
    Map IsolationForest decision_function score + SOH% → classification label.

    score: more negative = more anomalous
    soh:   SOH% from LSTM predictor
    """
    if score > -0.1:
        return "Normal"
    elif score > -0.3 or soh >= 80:
        return "Degrading"
    else:
        return "Failed"
