# Home Credit Project

Home Credit Project for the UofU MSBA Practice Capstone course.

## Project layout

```text
data/
  raw/          Original supplied files; do not modify
  interim/      Reusable cleaned or join-ready tables
  processed/    Modeling-ready data sets
docs/           Business context, data map, feature report, and EDA plan
notebooks/      Numbered exploratory, feature-engineering, modeling, and evaluation notebooks
src/            Reusable data-preparation, feature, modeling, and evaluation code
models/         Serialized models and model documentation
reports/figures/ Exported charts and final-report assets
tests/          Automated data and code checks
```

The current EDA notebook is [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb). It reads the original inputs from `data/raw/` and is designed to run from either the project root or the `notebooks/` directory.

## Data preparation

[`src/application_preparation.py`](src/application_preparation.py) is the reusable, EDA-driven preparation module for application data. It is imported by modeling notebooks or scripts so cleaning and feature creation are not copied or refit differently in each analysis. It does not make underwriting-policy decisions; the EDA's governance cautions still apply to external scores, demographic fields, and regional/address variables.

### Inputs and outputs

The module expects these original files, which must remain unmodified:

- `data/raw/application_train.csv`: 307,511 application rows, including `TARGET`.
- `data/raw/application_test.csv`: 48,744 application rows, without `TARGET`.

The module intentionally writes no files. It returns in-memory objects for the modeling workflow:

- `ApplicationPreparationState`: the training-fitted transformation parameters.
- `X_train`: a 307,511 × 276 feature DataFrame.
- `y_train`: a 307,511-row `TARGET` Series.
- `X_test`: a 48,744 × 276 feature DataFrame.

`SK_ID_CURR` is used to validate the application grain and is excluded from the model matrix. Therefore, one output row corresponds to each validated unique applicant/application key, while `TARGET` remains separate from `X_train`.

### EDA decisions implemented

| EDA decision | Script transformation and rationale |
| --- | --- |
| Q1: one row per `SK_ID_CURR`; keys are complete and unique | `validate_application_data()` rejects null or duplicate keys before transformation. |
| Q2: `DAYS_EMPLOYED = 365243` is a sentinel | Replaces the sentinel in the employment-duration field while retaining `employment_sentinel_flag`; it is not treated as a literal employment history. |
| Q2: `XNA` is an unknown category; test has a `-1` regional rating | Converts `XNA` to `__UNKNOWN__`; converts the invalid rating to an explicit missing category. Regional ratings are categorical, not median-imputed continuous values. |
| Q6: missingness is structured and informative | Adds missingness flags for every original application field, structural flags for car age and occupation, and total/external-score/bureau-enquiry missingness counts. Numeric median filling is paired with the original-missing flag so the model can distinguish an imputed value. |
| Q7: the employment sentinel is a distinct segment | Retains `employment_sentinel_flag` while deriving employment duration only for non-sentinel rows. |
| Q8: financial capacity fields and payment-to-income show non-flat patterns | Creates payment-to-income, credit-to-income, credit-to-goods-price, and annuity-to-credit ratios; zero denominators become missing rather than infinite. |
| Q9: age, employment, registration, and phone-change offsets need sign handling | Converts negative day offsets to positive years and creates training-derived quantile bins for age, employment, registration, and payment-to-income. |
| Q10: external scores and enquiry missing/zero/positive states differ | Creates external-score mean/missing count, bureau missing count, score quantile bins, and a missing/zero/positive state for each bureau-enquiry field. |
| Q11: address consistency may add information | Sums the six address-mismatch flags into `address_mismatch_count`; this remains subject to the EDA's proxy-risk review. |
| Q5: train and test differ in missingness and category support | Learns preprocessing only from training, maps unseen test categories to `__UNKNOWN__`, and reindexes output to the training-derived schema. |

### EDA decisions intentionally not implemented

- Q13's feature-governance decisions are not automated. The EDA marked demographic, external-score, regional/address, and document/contact fields as needing governance, fairness, provenance, or operational review. The script preserves them for controlled development; feature inclusion is a documented modeling/governance decision, not an automatic cleaning rule.
- Q14's historical child-table aggregates are not created because the six supplementary files were absent from the workspace. `join_aggregated_supplementary()` is supplied for future timing-audited tables that have first been aggregated to one row per `SK_ID_CURR`; it refuses joins that would duplicate applications.
- The module does not one-hot encode categorical features. Encoding is model-specific and should be fitted within the modeling pipeline or cross-validation fold, after this consistent preparation step.

### Train/test consistency

`fit_application_preparation(train)` creates an `ApplicationPreparationState` from training data only. It stores:

- `numeric_medians` for numeric imputation;
- `categorical_levels` for known-category support and unseen-category handling;
- `bin_edges` for quantile-bin thresholds;
- `missing_indicator_columns`; and
- `output_feature_columns`, the fixed ordered output schema.

`transform_application(frame, state)` uses those stored values without recalculating any statistics from validation or test rows. Thus, test missing values use training medians, test-only categories become `__UNKNOWN__`, and test values use training bin thresholds. The final schema is explicitly reindexed to `state.output_feature_columns`.

### How to run it

Run these function calls from the project root, in this order:

```python
import pandas as pd

from src.application_preparation import (
    fit_application_preparation,
    split_features_target,
    transform_application,
    validate_prepared_outputs,
)

train = pd.read_csv("data/raw/application_train.csv")
test = pd.read_csv("data/raw/application_test.csv")

# Fit all transformation values on the training partition only.
state = fit_application_preparation(train)
X_train, y_train = split_features_target(train, state)

# Apply exactly the same learned transformations to unlabeled test data.
X_test = transform_application(test, state)

# Confirm key, row-count, schema, and null-value invariants.
report = validate_prepared_outputs(train, test, X_train, X_test)
print(report)
```

The supplied-data validation report is:

```python
{
    'train_input_rows': 307511,
    'test_input_rows': 48744,
    'train_feature_rows': 307511,
    'test_feature_rows': 48744,
    'shared_feature_columns': 276,
    'train_null_values': 0,
    'test_null_values': 0,
    'train_keys_unique': True,
    'test_keys_unique': True,
    'identical_ordered_feature_columns': True,
}
```

This confirms that train and test have the same 276 feature columns (with `TARGET` kept outside the feature matrix) and that preparation preserved one row per validated `SK_ID_CURR`. For cross-validation, fit a new preparation state on each fold's training subset, then transform that fold's validation subset. This prevents validation-data leakage.

## Modeling notebook

[`notebooks/02_modeling.qmd`](notebooks/02_modeling.qmd) is the staged Python
modeling notebook. It establishes a majority-class benchmark (91.93% accuracy
but 0.500 AUC), then uses three-fold cross-validation to compare unweighted and
class-weighted logistic regression, a class-weighted random forest, and
histogram gradient boosting. On the 25,000-row exploration sample, governed
unweighted logistic regression led at 0.7563 AUC; gradient boosting was 0.7544.
After a 5,000-row randomized search selected `C = 0.0020008546`, full-
development five-fold confirmation chose the all-engineered logistic model
(0.7478 ± 0.0043 AUC), which earned 0.7537 on the untouched holdout. Models are
ranked by out-of-sample ROC-AUC rather than accuracy because `TARGET` is
imbalanced.

The notebook defaults to paused compute stages so expensive experiments are
never accidentally repeated. The local submission artifact is
`data/processed/home_credit_test_predictions.csv`; submit it manually to the
course Kaggle competition, then record the returned score in
[`docs/modeling_results.md`](docs/modeling_results.md). Render locally with
`quarto render notebooks/02_modeling.qmd`; commit the `.qmd` source, while
model files, submissions, and rendered HTML remain local/ignored.
