"""
Small standalone Flask microservice exposing the trained placement model as
/predict. Kept as its own service (not a function imported into the main
backend) so it has its own dependency set (scikit-learn/pandas) that the
core CRUD backend never needs to install, and so it could be scaled/deployed
independently of the main API.
"""
import os

import joblib
import pandas as pd
from flask import Flask, jsonify, request

import train

app = Flask(__name__)

_model = None


def get_model():
    """
    Lazy-loaded, cached at module scope. If no trained model file exists yet
    (first run, or a fresh clone before anyone has run train.py manually),
    train one on the fly from whatever's in the database right now — this
    means the ML service "just works" after `docker compose up` + seeding,
    without a separate required step, while `python train.py` remains the
    documented way to retrain after re-seeding.
    """
    global _model
    if _model is None:
        if not os.path.exists(train.MODEL_PATH):
            print("No trained model found — training one now from the current database...")
            train.main()
        _model = joblib.load(train.MODEL_PATH)
    return _model


@app.get("/health")
def health():
    return jsonify({"status": "ok", "model_loaded": _model is not None})


@app.post("/predict")
def predict():
    body = request.get_json(silent=True) or {}
    missing = [f for f in train.FEATURE_COLUMNS if body.get(f) is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    model = get_model()
    X = pd.DataFrame([{col: body[col] for col in train.FEATURE_COLUMNS}])
    probability = float(model.predict_proba(X)[0][1])

    return jsonify({"placement_probability": round(probability, 4)})


if __name__ == "__main__":
    get_model()  # fail fast / train immediately on startup rather than on first request
    app.run(port=6000, debug=True)
