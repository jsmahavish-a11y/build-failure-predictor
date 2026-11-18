# Build Failure Predictor

An ML model that predicts the risk of a CI build failing from commit-level features, served as a live REST API, containerized with Docker, and wired into GitHub Actions.

**Live API docs:** https://build-failure-predictor-latest.onrender.com/docs
(Hosted on a free plan, so the first request after inactivity can take about 50 seconds.)

**Container image:** `ghcr.io/jsmahavish-a11y/build-failure-predictor:latest`

## Problem
When a CI build fails, developers lose time waiting for results and debugging. This project estimates failure risk before the build result is known.

## How it works
1. Collected about 1,000 push-triggered GitHub Actions runs from public Python repos (flask, click, requests, pytest, httpx) using the GitHub API.
2. Converted them into 553 commit-level rows (51 with a failing workflow).
3. Features: files changed, lines added and deleted, test files changed, dependency files changed, commit message length, hour of day, previous commit failed, recent failure rate in the repo.
4. Trained a Random Forest with class weighting to handle the imbalance (about 9% failures).
5. Served the model with FastAPI and deployed it on Render.
6. Added a GitHub Actions workflow that calls the live API on every push to main and comments the risk level on the commit.
7. Containerized the API with Docker. A second workflow builds the image, smoke-tests `/predict` inside the container, and publishes it to GitHub Container Registry. The same image is deployed on Render.

## Results
Time-based split (train on older commits, test on the newest 20%):

| Metric | Value |
|---|---|
| Random-guess baseline (average precision) | 0.09 |
| Model (average precision) | 0.38 |

### Cross-repository test (leave-one-repo-out)
Each repository was held out in turn and the model was trained on the other four.

| Held-out repo | Failures | Random baseline | Model |
|---|---|---|---|
| click | 3 | 0.019 | 0.020 |
| flask | 34 | 0.453 | 0.462 |
| requests | 7 | 0.096 | 0.123 |
| pytest | 7 | 0.028 | 0.058 |

The model does not clearly beat the random baseline on repositories it has not seen. The earlier scores come mostly from repositories seen during training, and failure history likely acts partly as a repository identifier (Flask holds 34 of the 51 failures). The model is best viewed as a per-repository risk estimator that needs that repository's own history, not a general-purpose predictor.

### Comparison with a simple rule
Predicting "fail if the previous commit failed" gives precision 0.46, recall 0.46 and F1 0.46 on the same data, essentially matching the model (F1 0.46). Failures occur in streaks (a broken build often stays broken for several commits), so most of the model's signal comes from failure persistence.

Restricting to the 503 commits that follow a passing commit (28 failures, random baseline 0.056), the model reaches an average precision of 0.153, so commit features may add a small amount of signal beyond streaks. With only 28 failures and shuffled cross-validation, this is indicative, not conclusive.

### Ablation study
5-fold cross-validation on 553 commits (51 failures). Random-guess baseline for average precision is 0.09.

| Features | Average precision | Recall | F1 |
|---|---|---|---|
| All features | 0.458 | 0.545 | 0.463 |
| Only failure history | 0.423 | 0.547 | 0.494 |
| Without size features | 0.441 | 0.529 | 0.447 |
| Without failure history | 0.335 | 0.371 | 0.342 |
| Without context features | 0.451 | 0.567 | 0.487 |

Removing failure-history features causes the largest drop. Differences of about 0.02 are within noise given only 51 failures. Because most failures come from one repository, the history features may partly act as a repository identifier; a leave-one-repo-out test is the next planned check.

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

## Run locally with Docker

```bash
docker pull ghcr.io/jsmahavish-a11y/build-failure-predictor:latest
docker run -p 8000:8000 ghcr.io/jsmahavish-a11y/build-failure-predictor:latest
```

Then open http://localhost:8000/docs

## Limitations
- Small dataset (51 failing commits), and most failures come from one repo, so results are noisy.
- The test set has only 10 failures; treat the score as indicative.
- `failure_risk` is a relative risk score, not a calibrated probability.
- Failures can come from flaky tests or network issues that commit features cannot capture.
- Level thresholds (0.25 and 0.5) were chosen by hand.
- The model only sees commit-level signals and recent failure history, so non-code changes (for example images) are scored LOW.
- Redeploying the Render service after an image update is manual.
- Does not generalise to unseen repositories (see the cross-repository test).

## Tech stack
Python, pandas, scikit-learn, FastAPI, Docker, GitHub Actions, GitHub Container Registry, Render, GitHub API

## Next steps
AWS deployment, extending the Actions comment to pull requests, more repos and data, an ablation study and model comparison, explaining each prediction.
