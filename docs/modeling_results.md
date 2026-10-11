# Modeling results record

Populate this record from the rendered `notebooks/02_modeling.qmd` after the
approved experiment sequence has run. Do not enter estimated or invented
results.

## Cross-validated comparison

| Model | Feature set | Imbalance treatment | CV folds / sample | Mean AUC | AUC SD | Mean accuracy | Notes |
|---|---|---|---|---:|---:|---:|---|
| Majority-class baseline | n/a | None | 3 / 25,000 | 0.5000 | 0.0000 | 0.9193 | Accuracy is the non-default prevalence, but there is no ranking ability. |
| Logistic regression | Governed candidate | None | 3 / 25,000 | 0.7563 | 0.0023 | 0.9193 | Best exploratory AUC. |
| Logistic regression | All engineered | None | 3 / 25,000 | 0.7542 | 0.0052 | 0.9192 | Selected after full-development feature confirmation. |
| Logistic regression | All engineered | `class_weight="balanced"` | 3 / 25,000 | 0.7533 | 0.0056 | 0.7036 | Class weighting did not improve AUC. |
| Random forest | All engineered | `balanced_subsample` | 3 / 25,000 | 0.7489 | 0.0058 | 0.8471 | |
| Histogram gradient boosting | All engineered | None | 3 / 25,000 | 0.7544 | 0.0043 | 0.9192 | |

## Selected model

- **Model and feature set:** Unweighted L2-regularized logistic regression; all engineered application features.
- **Why selected:** It had a strong exploratory AUC, was competitive with gradient boosting, and the all-engineered feature set won full-development feature confirmation. External-score use remains subject to governance approval.
- **Randomized-search parameters:** `C = 0.0020008545549484993`, selected from 25 randomized draws on 5,000 rows using three folds.
- **Five-fold development CV AUC (mean ± SD):** 0.7478 ± 0.0043 for all engineered features. The governed candidate subset was 0.7448 ± 0.0040; no-external-scores was 0.6845 ± 0.0037.
- **Untouched holdout AUC:** 0.7537.

## Kaggle submission

- **Competition:** _fill_
- **Submission file:** `data/processed/home_credit_test_predictions.csv`
- **Submission date:** _fill_
- **Public score:** _fill_
- **Private/final score:** _fill when available_

## Limitations

- The supplied application data does not include an application timestamp, so
  this is not a temporal validation estimate.
- Test labels are unavailable locally; the Kaggle result is external evidence,
  not a local test AUC.
- Supplementary historical tables were not present in the current source data.
  Aggregate and timing-audit them before any one-row-per-application join.
