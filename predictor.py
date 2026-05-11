# predictor.py
import pickle
import numpy as np
from datetime import datetime, timedelta

# Load your trained model once at startup
with open("best_model.pkl", "rb") as f:
    bundle = pickle.load(f)

_model    = bundle["model"]
_scaler   = bundle["scaler"]
_features = bundle["feature_cols"]


def compute_score_trend(scores: list) -> float:
    """Compute slope of quiz scores across attempts."""
    n = len(scores)
    if n >= 3:
        slope = np.polyfit(range(n), scores, 1)[0]
        return round(float(np.clip(slope, -10, 10)), 2)
    elif n == 2:
        return round(float(np.clip(scores[1] - scores[0], -10, 10)), 2)
    return 0.0


def compute_retention(avg_score: float, days_since: int) -> float:
    """Approximate Ebbinghaus retention score."""
    import math
    S = (avg_score / 100.0) * 10.0   # rough memory strength
    retention = math.exp(-days_since / max(S, 0.1)) * 100
    return round(min(100.0, max(0.0, retention)), 2)


def predict_revision(
    student_historical_avg: float,   # mean score across all concepts
    diff_numeric: int,               # 1=Easy 2=Medium 3=Hard
    all_scores_this_concept: list,   # list of all quiz scores on this concept
    days_since_last_attempt: int,
) -> dict:
    """
    Call this after every quiz attempt.
    Returns revision date and urgency.
    """
    n       = len(all_scores_this_concept)
    avg_sc  = round(float(np.mean(all_scores_this_concept)), 2)
    last_sc = all_scores_this_concept[-1]
    trend   = compute_score_trend(all_scores_this_concept)
    ret     = compute_retention(avg_sc, days_since_last_attempt)

    row = {
        "student_historical_avg":   student_historical_avg,
        "diff_numeric":             diff_numeric,
        "num_attempts":             n,
        "latest_quiz_score":        last_sc,
        "avg_quiz_score":           avg_sc,
        "score_trend":              trend,
        "days_since_last_attempt":  days_since_last_attempt,
        "retention_score":          ret,
    }

    X         = np.array([[row[f] for f in _features]])
    days_pred = float(_model.predict(_scaler.transform(X))[0])
    days_pred = round(max(1.0, days_pred), 1)

    revision_date = datetime.today() + timedelta(days=days_pred)

    return {
        "revise_in_days": days_pred,
        "revision_date":  revision_date.strftime("%Y-%m-%d"),
        "urgency":        (
            "critical" if days_pred <= 3 else
            "soon"     if days_pred <= 7 else
            "moderate" if days_pred <= 30 else
            "good"
        )
    }