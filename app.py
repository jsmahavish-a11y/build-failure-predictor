from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import pandas as pd

app = FastAPI(title="Build Failure Predictor")
model = joblib.load("model.pkl")

COLS = ["n_files", "additions", "deletions", "test_files", "dep_files",
        "msg_len", "hour", "prev_failed", "recent_fail_rate"]


class Commit(BaseModel):
    n_files: int
    additions: int
    deletions: int
    test_files: int
    dep_files: int
    msg_len: int
    hour: int
    prev_failed: int
    recent_fail_rate: float


@app.get("/")
def home():
    return {"message": "Build Failure Predictor API is running"}


@app.post("/predict")
def predict(commit: Commit):
    row = pd.DataFrame([commit.model_dump()])[COLS]
    risk = float(model.predict_proba(row)[0][1])
    level = "HIGH" if risk >= 0.5 else "MEDIUM" if risk >= 0.25 else "LOW"
    return {"failure_risk": round(risk, 3), "level": level}
