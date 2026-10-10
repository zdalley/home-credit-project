# Modeling results record

Populate this record from the rendered `notebooks/02_modeling.qmd` after the
approved experiment sequence has run. Do not enter estimated or invented
results.

## Cross-validated comparison

| Model | Feature set | Imbalance treatment | CV folds / sample | Mean AUC | AUC SD | Mean accuracy | Notes |
|---|---|---|---|---:|---:|---:|---|
| Majority-class baseline | n/a | None | 3 / _fill_ | _fill_ | _fill_ | _fill_ | Expected AUC is 0.500; accuracy reflects the majority class. |
| Logistic regression | _fill_ | None | 3 / _fill_ | _fill_ | _fill_ | _fill_ | |
| Logistic regression | _fill_ | `class_weight="balanced"` | 3 / _fill_ | _fill_ | _fill_ | _fill_ | |
| Random forest | _fill_ | `balanced_subsample` | 3 / _fill_ | _fill_ | _fill_ | _fill_ | |
| Histogram gradient boosting | _fill_ | None | 3 / _fill_ | _fill_ | _fill_ | _fill_ | |

## Selected model

- **Model and feature set:** _fill_
- **Why selected:** _fill: explain AUC, variability, runtime, and governance trade-offs._
- **Randomized-search parameters:** _fill_
- **Five-fold development CV AUC (mean ± SD):** _fill_
- **Untouched holdout AUC:** _fill_

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
