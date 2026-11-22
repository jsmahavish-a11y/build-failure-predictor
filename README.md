# Build Failure Predictor

An ML model that estimates the risk of a CI build failing from commit-level features and recent failure history. It is served as a REST API, containerized with Docker, and wired into GitHub Actions so every push to `main` gets a risk comment.

**Live API docs:** https://build-failure-predictor-latest.onrender.com/docs
(Hosted on a free plan, so the first request after inactivity can take about 50 seconds.)

**Container image:** `ghcr.io/jsmahavish-a11y/build-failure-predictor:latest`

## Problem
When a CI build fails, developers lose time waiting for results and debugging. This project estimates failure risk before the build result is known.

## How it works
1. Collected push-triggered GitHub Actions runs from 15 public Python repositories (flask, click, requests, pytest, httpx, fastapi, django, pandas, scikit-learn, black, pip, poetry, sqlalchemy, aiohttp, scrapy) using the GitHub API.
2. Converted them into 1,496 commit-level rows (149 with a failing workflow, about 10%).
3. Features: files changed, lines added and deleted, test files changed, dependency files changed, commit message length, hour of day, whether the previous commit failed, and the recent failure rate in the repository.
4. Trained a Random Forest with class weighting to handle the imbalance.
5. Served the model with FastAPI and deployed it on Render.
6. A GitHub Actions workflow calls the live API on every push to `main` and comments the risk level on the commit.
7. A second workflow builds the Docker image, smoke-tests `/predict` inside the container, and publishes the image to GitHub Container Registry. The same image is deployed on Render.

## API
`POST /predict`

```json
{
  "n_files": 25, "additions": 800, "deletions": 120,
  "test_files": 0, "dep_files": 1, "msg_len": 12,
  "hour": 23, "prev_failed": 1, "recent_fail_rate": 0.3
}
```

Response: `{"failure_risk": 0.89, "level": "HIGH"}`

## Run locally with Docker

```bash
docker pull ghcr.io/jsmahavish-a11y/build-failure-predictor:latest
docker run -p 8000:8000 ghcr.io/jsmahavish-a11y/build-failure-predictor:latest
```

Then open http://localhost:8000/docs

## Evaluation

The random-guess baseline for average precision equals the failure rate, so it differs by repository. Higher is better.

### Cross-repository test (leave-one-repo-out)
Data: 1,496 commits from 15 repositories (149 failures). Each repository with at least 10 failures was held out in turn, and the model was trained on the other 14.

| Held-out repo | Failures | Random baseline | Rule: previous commit failed | Rule: recent failure rate | Model |
|---|---|---|---|---|---|
| aiohttp | 19 | 0.151 | 0.163 | 0.187 | 0.272 |
| flask | 31 | 0.463 | 0.670 | 0.526 | 0.599 |
| pip | 18 | 0.120 | 0.116 | 0.137 | 0.242 |
| scrapy | 25 | 0.291 | 0.356 | 0.368 | 0.410 |
| sqlalchemy | 19 | 0.127 | 0.251 | 0.144 | 0.200 |
| Average | 22 | 0.230 | 0.311 | 0.272 | 0.345 |

The model beats the random baseline on all five held-out repositories, about 1.5 times on average, and is slightly ahead of the one-line rules on average but not on every repository: on flask and sqlalchemy the "previous commit failed" rule is better. A possible explanation is that failures come in streaks in some repositories, but this was not tested. Without the failure-history features the average falls to 0.270, below baseline on flask and scrapy. Five extra commit-content features (message keywords, file types, number of folders) did not help (0.330 with them against 0.345 without). Each held-out repository has only 18 to 31 failures, so differences of about 0.03 to 0.05 are not meaningful.

### Earlier experiments on the first, smaller dataset
These used 5 repositories and 553 commits (51 failures), before the dataset was expanded.

Time-based split (train on older commits, test on the newest 20%, 10 failures in the test set): average precision 0.38 against a 0.09 random baseline.

Ablation (5-fold cross-validation):

| Features | Average precision | Recall | F1 |
|---|---|---|---|
| All features | 0.458 | 0.545 | 0.463 |
| Only failure history | 0.423 | 0.547 | 0.494 |
| Without size features | 0.441 | 0.529 | 0.447 |
| Without failure history | 0.335 | 0.371 | 0.342 |
| Without context features | 0.451 | 0.567 | 0.487 |

Removing failure history caused the largest drop. On that dataset, predicting "fail if the previous commit failed" matched the model (F1 0.46). A leave-one-repository-out test on those five repositories stayed close to random, which motivated collecting more repositories.

## Limitations
- Limited data: 149 failing commits across 15 repositories, and per-repository results are noisy.
- Only modestly better than random on held-out repositories (about 1.5 times), and only slightly ahead of a one-line "previous commit failed" rule, not on every repository.
- The model relies on a repository's own recent build history.
- `failure_risk` is a relative risk score, not a calibrated probability.
- Failures can come from flaky tests or network issues that commit features cannot capture.
- Level thresholds (0.25 and 0.5) were chosen by hand.
- The model only sees commit-level signals and recent failure history, so non-code changes (for example images) are scored LOW.
- Redeploying the Render service after an image update is manual.

## Tech stack
Python, pandas, scikit-learn, FastAPI, Docker, GitHub Actions, GitHub Container Registry, Render, GitHub API

## Next steps
Collect more failing commits, check whether the streak explanation holds, compare against Logistic Regression and XGBoost, explain each prediction, extend the Actions comment to pull requests, and deploy on AWS.
