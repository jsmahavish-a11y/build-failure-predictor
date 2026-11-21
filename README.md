# Build Failure Predictor

An ML model that estimates the risk of a CI build failing from commit-level features and recent failure history. It is served as a REST API, containerized with Docker, and wired into GitHub Actions so every push to `main` gets a risk comment.

**Live API docs:** https://build-failure-predictor-latest.onrender.com/docs
(Hosted on a free plan, so the first request after inactivity can take about 50 seconds.)

**Container image:** `ghcr.io/jsmahavish-a11y/build-failure-predictor:latest`

## Problem
When a CI build fails, developers lose time waiting for results and debugging. This project estimates failure risk before the build result is known.

## How it works
1. Collected about 1,000 push-triggered GitHub Actions runs from five public Python repositories (flask, click, requests, pytest, httpx) using the GitHub API.
2. Converted them into 553 commit-level rows (51 with a failing workflow).
3. Features: files changed, lines added and deleted, test files changed, dependency files changed, commit message length, hour of day, whether the previous commit failed, and the recent failure rate in the repository.
4. Trained a Random Forest with class weighting to handle the imbalance (about 9% failures).
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

Response: `{"failure_risk": 0.905, "level": "HIGH"}`

## Run locally with Docker

```bash
docker pull ghcr.io/jsmahavish-a11y/build-failure-predictor:latest
docker run -p 8000:8000 ghcr.io/jsmahavish-a11y/build-failure-predictor:latest
```

Then open http://localhost:8000/docs

## Evaluation
The time-based split, ablation and simple-rule results below the cross-repository test come from the first, smaller dataset (5 repositories, 553 commits, 51 failures). The cross-repository results on 15 repositories (1,496 commits, 149 failures) are the most reliable.
The random-guess baseline for average precision is about 0.09, because only about 9% of commits fail.

### Time-based split
Trained on older commits and tested on the newest 20% (10 failures in the test set).

| Metric | Value |
|---|---|
| Random-guess baseline (average precision) | 0.09 |
| Model (average precision) | 0.38 |

### Ablation study
5-fold cross-validation on 553 commits (51 failures).

| Features | Average precision | Recall | F1 |
|---|---|---|---|
| All features | 0.458 | 0.545 | 0.463 |
| Only failure history | 0.423 | 0.547 | 0.494 |
| Without size features | 0.441 | 0.529 | 0.447 |
| Without failure history | 0.335 | 0.371 | 0.342 |
| Without context features | 0.451 | 0.567 | 0.487 |

Removing the failure-history features causes the largest drop. Differences of about 0.02 are within noise given only 51 failures.

### Comparison with simple rules
On the same five held-out repositories (15-repository training data), average precision for two one-line rules is compared with the model.

| Method | Average precision |
|---|---|
| Random guess | 0.230 |
| Rule: fail if previous commit failed | 0.311 |
| Rule: recent failure rate of the repository | 0.272 |
| Model (old features + history) | 0.345 |

The model is slightly ahead on average but not on every repository. On aiohttp and pip the rules are close to random while the model scores about 1.8 to 2 times the baseline. On flask and sqlalchemy the "previous commit failed" rule beats the model. A possible explanation is that failures come in streaks in some repositories, but this was not tested. With 18 to 31 failures per held-out repository, the 0.03 gap between model and rule is within noise.
Restricting to the 503 commits that follow a passing commit (28 failures, random baseline 0.056), the model reaches an average precision of 0.153, so commit features may add a small amount of signal beyond streaks. With only 28 failures and shuffled cross-validation, this is indicative, not conclusive.

### Cross-repository test (leave-one-repo-out)
Data: 1,496 commits from 15 repositories (149 failures). Each repository with at least 10 failures was held out in turn, and the model was trained on the other 14. The score is average precision; higher is better.

| Held-out repo | Failures | Random baseline | Model (old features + history) |
|---|---|---|---|
| aiohttp | 19 | 0.151 | 0.272 |
| flask | 31 | 0.463 | 0.599 |
| pip | 18 | 0.120 | 0.242 |
| scrapy | 25 | 0.291 | 0.410 |
| sqlalchemy | 19 | 0.127 | 0.200 |
| Average | 22 | 0.230 | 0.345 |

With this larger and more varied training set the model beats the random baseline on all five held-out repositories, about 1.5 times on average, which an earlier 5-repository version did not. Without the failure-history features the average falls to 0.270 and the model drops below baseline on flask and scrapy. Five extra commit-content features (message keywords, file types, number of folders) did not help (0.330 with them against 0.345 without), which is within noise. Each held-out repository has only 18 to 31 failures, so differences of about 0.03 to 0.05 are not meaningful.

The model does not clearly beat the random baseline on repositories it has not seen. Failure history likely acts partly as a repository identifier (Flask holds 34 of the 51 failures). The model is best viewed as a per-repository risk estimator that needs that repository's own history, not a general-purpose predictor.

## Limitations
- Small dataset (51 failing commits), and most failures come from one repository, so results are noisy.
- Only modestly better than random on held-out repositories (about 1.5 times), and it relies on a repository's own recent build history.
- Most of the signal is failure persistence, which a one-line rule also captures.
- `failure_risk` is a relative risk score, not a calibrated probability.
- Failures can come from flaky tests or network issues that commit features cannot capture.
- Level thresholds (0.25 and 0.5) were chosen by hand.
- The model only sees commit-level signals and recent failure history, so non-code changes (for example images) are scored LOW.
- Redeploying the Render service after an image update is manual.
- Limited data: 149 failing commits across 15 repositories; per-repository results are noisy.
- Only modestly better than a one-line "previous commit failed" rule, and not better on every repository.

## Tech stack
Python, pandas, scikit-learn, FastAPI, Docker, GitHub Actions, GitHub Container Registry, Render, GitHub API

## Next steps
Collect many more repositories with more failures, add features that describe commit content (message keywords, file types, author history), re-run the cross-repository test, explain each prediction, extend the Actions comment to pull requests, and deploy on AWS.
