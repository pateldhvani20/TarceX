from pathlib import Path

import joblib
import numpy as np

from backend import config


_MODEL = None


def load_model():
    global _MODEL

    if _MODEL is None:
        model_path = Path(config.model_path)

        if not model_path.exists():
            raise FileNotFoundError(
                f"Anomaly model not found: {model_path}"
            )

        _MODEL = joblib.load(model_path)

    return _MODEL


def predict(features: list[float]) -> tuple[str, float]:
    """
    Run the real scikit-learn IsolationForest model.

    Returns:
        (label, score)
    """

    model = load_model()

    values = np.asarray(
        features,
        dtype=float,
    ).reshape(1, -1)

    prediction = int(model.predict(values)[0])

    score = float(
        model.decision_function(values)[0]
    )

    label = (
        "anomalous"
        if prediction == -1
        else "normal"
    )

    return label, score