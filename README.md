# Build Failure Predictor

An ML model that predicts the risk of a CI build failing from commit-level features, served as a live REST API.

**Live API docs:** https://build-failure-predictor-latest.onrender.com/docs

## Problem
When a CI build fails, developers lose time waiting for results and debugging. This project estimates failure risk before the build result is known.

## How it works
1. Collected about 1,000 push-triggered GitHub Actions runs from public Python repos (flask, click, requests, pytest, httpx) using the GitHub API.
2. Converted them into 553 commit-level rows (51 with a failing workflow).
3. Features: files changed, lines added and deleted, test files changed, dependency files changed, commit message length, hour of day, previous commit failed, recent failure rate in the repo.
4. Trained a Random Forest with class weighting to handle the imbalance (about 9% failures).
5. Served the model with FastAPI and deployed it on Render.
6. Added a GitHub Actions workflow that calls the live API on every push to main and comments the risk level on the commit.
7. Containerized the API with Docker; a GitHub Actions workflow builds the image, smoke-tests /predict inside the container, and publishes it to GitHub Container Registry. The same image is deployed on Render.

## Results
Time-based split (train on older commits, test on the newest 20%):

| Metric | Value |
|---|---|
| Random-guess baseline (average precision) | 0.09 |
| Model (average precision) | 0.38 |

Failure-history features gave the largest improvement over using change-size features alone.

## API
`POST /predict`

```json
{
  "n_files": 25, "additions": 800, "deletions": 120,
  "test_files": 0, "dep_files": 1, "msg_len": 12,
  "hour": 23, "prev_failed": 1, "recent_fail_rate": 0.3
}
```

Response: `{"failure_risk": 0.905, "level": "HIGH"}`

## Limitations
- Small dataset (51 failing commits), and most failures come from one repo, so results are noisy.
- The test set has only 10 failures; treat the score as indicative.
- `failure_risk` is a relative risk score, not a calibrated probability.
- Failures can come from flaky tests or network issues that commit features cannot capture.
- Level thresholds (0.25 and 0.5) were chosen by hand.
- The model only sees commit-level signals and recent failure history, so non-code changes (for example images) are scored LOW.

## Tech stack
Python, pandas, scikit-learn, FastAPI, Docker, GitHub Actions, GitHub Container Registry, Render, GitHub API

## Next steps
AWS deployment (needs an AWS account), extending the Actions comment to pull requests, more repos and data, ablation study and model comparison.
