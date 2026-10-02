"""Train/test-consistent preparation for Home Credit application data.

The choices in this module intentionally trace to ``notebooks/01_eda.ipynb``.
It is not a lending-policy approval: external scores, demographic fields, and
regional/address fields require the governance review recorded in that notebook
before they are used in an underwriting model.

Typical use
-----------
>>> state = fit_application_preparation(application_train)
>>> X_train = transform_application(application_train, state)
>>> X_test = transform_application(application_test, state)

``X_train`` and ``X_test`` have identical columns.  The target is deliberately
kept separate from the feature matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


TARGET_COLUMN = "TARGET"
ID_COLUMN = "SK_ID_CURR"
EMPLOYMENT_SENTINEL = 365243
MISSING_CATEGORY = "__MISSING__"
UNKNOWN_CATEGORY = "__UNKNOWN__"

EXTERNAL_SCORE_COLUMNS = ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3")
BUREAU_ENQUIRY_COLUMNS = (
    "AMT_REQ_CREDIT_BUREAU_HOUR",
    "AMT_REQ_CREDIT_BUREAU_DAY",
    "AMT_REQ_CREDIT_BUREAU_WEEK",
    "AMT_REQ_CREDIT_BUREAU_MON",
    "AMT_REQ_CREDIT_BUREAU_QRT",
    "AMT_REQ_CREDIT_BUREAU_YEAR",
)
REGIONAL_RATING_COLUMNS = ("REGION_RATING_CLIENT", "REGION_RATING_CLIENT_W_CITY")
ADDRESS_MISMATCH_COLUMNS = (
    "REG_REGION_NOT_LIVE_REGION",
    "REG_REGION_NOT_WORK_REGION",
    "LIVE_REGION_NOT_WORK_REGION",
    "REG_CITY_NOT_LIVE_CITY",
    "REG_CITY_NOT_WORK_CITY",
    "LIVE_CITY_NOT_WORK_CITY",
)

# Q8, Q9, and Q10 used five equal-frequency bins in the EDA.  Bins below use
# the same idea, but their edges are learned exclusively from training data.
BINNED_FEATURES = (
    "age_years",
    "employment_years",
    "registration_years",
    "requested_payment_to_income",
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
)


@dataclass(frozen=True)
class ApplicationPreparationState:
    """Values learned from the training partition and reused for later data.

    Attributes:
        raw_feature_columns: Input/model-feature names before fitted processing.
        output_feature_columns: Fixed ordered schema returned by transformation.
        numeric_medians: Training-only numeric imputation values.
        categorical_levels: Training-only category support for unknown handling.
        bin_edges: Training-only quantile thresholds for binned features.
        missing_indicator_columns: Fields that receive missingness indicators.
    """

    raw_feature_columns: tuple[str, ...]
    output_feature_columns: tuple[str, ...]
    numeric_medians: Mapping[str, float]
    categorical_levels: Mapping[str, frozenset[str]]
    bin_edges: Mapping[str, tuple[float, ...]]
    missing_indicator_columns: tuple[str, ...]


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    """Ensure an input frame contains required columns.

    Args:
        frame: DataFrame to inspect without modifying it.
        columns: Column names required by the calling transformation.

    Returns:
        ``None``. Raises ``ValueError`` listing any absent columns.
    """
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Application data is missing required columns: {missing}")


def validate_application_data(frame: pd.DataFrame, *, require_target: bool = False) -> None:
    """Validate an application input without changing it.

    Args:
        frame: One row per application, with ``SK_ID_CURR`` and required day fields.
        require_target: Require the training-only ``TARGET`` column when true.

    Returns:
        ``None``. Raises ``ValueError`` for missing columns, duplicate/null keys,
        or undocumented positive employment-day values.

    EDA rationale: Q1 established the one-row-per-application key requirement;
    Q2 documented the only permitted positive ``DAYS_EMPLOYED`` value.
    """
    required = {ID_COLUMN, "DAYS_BIRTH", "DAYS_EMPLOYED"}
    if require_target:
        required.add(TARGET_COLUMN)
    _require_columns(frame, required)

    if frame[ID_COLUMN].isna().any() or frame[ID_COLUMN].duplicated().any():
        raise ValueError("SK_ID_CURR must be non-null and unique at application grain.")

    # EDA Q2: positive employment values are only valid for the documented
    # 365243 sentinel.  Fail early for a new unexplained value.
    invalid_employment = frame["DAYS_EMPLOYED"].gt(0) & frame["DAYS_EMPLOYED"].ne(EMPLOYMENT_SENTINEL)
    if invalid_employment.any():
        raise ValueError("DAYS_EMPLOYED contains positive values other than the 365243 sentinel.")


def clean_application_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply non-modeling cleaning decisions recorded in EDA Q2 and Q7.

    Args:
        frame: Raw application rows containing the EDA-checked fields.

    Returns:
        A copy of ``frame`` with documented invalid/sentinel values normalized.

    Decisions implemented:

    * ``DAYS_EMPLOYED == 365243`` is replaced with missing *only in the
      duration field*; ``employment_sentinel_flag`` is added later so this
      distinct, mostly-pensioner segment is retained.
    * The test-only ``REGION_RATING_CLIENT_W_CITY == -1`` is invalid under the
      documented 1--3 domain and becomes an explicit missing category, not a
      real rating level or a median-imputed numeric rating.
    * ``XNA`` is an explicit unknown category, rather than a substantive level.
    """
    validate_application_data(frame)
    cleaned = frame.copy()
    # Keep this signal before masking the sentinel in the duration field.
    cleaned["employment_sentinel_flag"] = cleaned["DAYS_EMPLOYED"].eq(EMPLOYMENT_SENTINEL).astype("int8")
    cleaned["DAYS_EMPLOYED"] = cleaned["DAYS_EMPLOYED"].mask(
        cleaned["DAYS_EMPLOYED"].eq(EMPLOYMENT_SENTINEL)
    )
    if "REGION_RATING_CLIENT_W_CITY" in cleaned:
        cleaned["REGION_RATING_CLIENT_W_CITY"] = cleaned["REGION_RATING_CLIENT_W_CITY"].mask(
            cleaned["REGION_RATING_CLIENT_W_CITY"].eq(-1)
        )
    # Nullable integers keep valid ratings represented consistently in train
    # and test after the invalid test value above is masked.
    for column in REGIONAL_RATING_COLUMNS:
        if column in cleaned:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").astype("Int64")
    object_columns = cleaned.select_dtypes(include=["object", "string"]).columns
    for column in object_columns:
        cleaned[column] = cleaned[column].replace("XNA", UNKNOWN_CATEGORY)
    return cleaned


def create_application_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Create features supported by the EDA, before train-fitted processing.

    Args:
        frame: Cleaned application rows. It may include ``TARGET``, which is
            passed through unchanged and is not used to calculate features.

    Returns:
        A copy of ``frame`` with deterministic, row-level engineered features.

    Day offsets are negative relative to application date (EDA Q2/Q9), so
    derived ages and durations are expressed as positive years.  Denominators
    of zero produce missing values, which are subsequently handled with a
    training-only median plus a missingness indicator.
    """
    _require_columns(frame, {"DAYS_BIRTH", "DAYS_EMPLOYED"})
    featured = frame.copy()
    original_employed = frame["DAYS_EMPLOYED"]
    if "employment_sentinel_flag" not in featured:
        featured["employment_sentinel_flag"] = original_employed.eq(EMPLOYMENT_SENTINEL).astype("int8")

    # EDA Q7/Q9: preserve the sentinel separately and never interpret it as a
    # 1,000-year employment history.
    employment_days = original_employed.mask(original_employed.eq(EMPLOYMENT_SENTINEL))
    featured["age_years"] = -featured["DAYS_BIRTH"] / 365.25
    featured["employment_years"] = -employment_days / 365.25
    for raw_column, feature_name in (
        ("DAYS_REGISTRATION", "registration_years"),
        ("DAYS_ID_PUBLISH", "id_published_years"),
        ("DAYS_LAST_PHONE_CHANGE", "phone_change_years"),
    ):
        if raw_column in featured:
            featured[feature_name] = -featured[raw_column] / 365.25

    # EDA Q8: requested-payment-to-income was explicitly investigated.  The
    # related credit capacity ratios use the same supplied application amounts.
    if {"AMT_ANNUITY", "AMT_INCOME_TOTAL"}.issubset(featured):
        featured["requested_payment_to_income"] = _safe_divide(
            featured["AMT_ANNUITY"], featured["AMT_INCOME_TOTAL"]
        )
    if {"AMT_CREDIT", "AMT_INCOME_TOTAL"}.issubset(featured):
        featured["credit_to_income"] = _safe_divide(featured["AMT_CREDIT"], featured["AMT_INCOME_TOTAL"])
    if {"AMT_CREDIT", "AMT_GOODS_PRICE"}.issubset(featured):
        featured["credit_to_goods_price"] = _safe_divide(featured["AMT_CREDIT"], featured["AMT_GOODS_PRICE"])
    if {"AMT_ANNUITY", "AMT_CREDIT"}.issubset(featured):
        featured["annuity_to_credit"] = _safe_divide(featured["AMT_ANNUITY"], featured["AMT_CREDIT"])

    # EDA Q6/Q10: joint external-score and enquiry missingness is informative.
    available_scores = [c for c in EXTERNAL_SCORE_COLUMNS if c in featured]
    if available_scores:
        featured["external_score_missing_count"] = featured[available_scores].isna().sum(axis=1).astype("int8")
        featured["external_score_mean"] = featured[available_scores].mean(axis=1)
    available_enquiries = [c for c in BUREAU_ENQUIRY_COLUMNS if c in featured]
    if available_enquiries:
        featured["bureau_enquiry_missing_count"] = featured[available_enquiries].isna().sum(axis=1).astype("int8")
        # EDA Q10 compared missing, zero, and positive enquiries separately.
        # Keep those states as categorical features in addition to the count.
        for column in available_enquiries:
            featured[f"{column}_state"] = np.select(
                [featured[column].isna(), featured[column].eq(0)],
                [MISSING_CATEGORY, "zero"],
                default="positive",
            )

    # EDA Q6 also compared the overall application-field missingness burden.
    source_features = [column for column in frame.columns if column not in {ID_COLUMN, TARGET_COLUMN}]
    featured["total_missing_feature_count"] = frame[source_features].isna().sum(axis=1)

    # EDA Q11: the six address inconsistency flags were summarized as a count.
    available_address_flags = [c for c in ADDRESS_MISMATCH_COLUMNS if c in featured]
    if available_address_flags:
        featured["address_mismatch_count"] = featured[available_address_flags].sum(axis=1)

    # EDA Q6 structural-missingness findings are made explicit rather than
    # allowing a later imputation value to conceal them.
    for column, feature_name in (("OWN_CAR_AGE", "own_car_age_missing_flag"), ("OCCUPATION_TYPE", "occupation_missing_flag")):
        if column in featured:
            featured[feature_name] = featured[column].isna().astype("int8")
    return featured


def fit_application_preparation(train: pd.DataFrame, *, n_bins: int = 5) -> ApplicationPreparationState:
    """Learn all imputation/category/bin parameters from labeled training data.

    Args:
        train: Raw labeled application training data, one row per ``SK_ID_CURR``.
        n_bins: Requested number of equal-frequency bins; defaults to the five
            bins used in EDA Q8--Q10.

    Returns:
        ``ApplicationPreparationState`` containing only training-derived
        medians, category levels, bin edges, indicator schema, and output order.

    ``TARGET`` is never used to calculate a transformation.  It is accepted
    only because training files contain it and is excluded from model inputs.
    """
    validate_application_data(train, require_target=True)
    prepared = create_application_features(clean_application_values(train))
    raw_features = tuple(c for c in prepared.columns if c not in {ID_COLUMN, TARGET_COLUMN})
    candidate = prepared.loc[:, raw_features]
    # EDA Q11 treated regional ratings as discrete groups.  Encoding them as
    # categories avoids inventing a numeric midpoint when the test-only -1 is
    # converted to missing.
    forced_categorical = set(REGIONAL_RATING_COLUMNS).intersection(candidate.columns)
    numeric_columns = [
        c for c in candidate.select_dtypes(include=[np.number, "bool"]).columns
        if c not in forced_categorical
    ]
    categorical_columns = [c for c in candidate.columns if c not in numeric_columns]
    medians = candidate[numeric_columns].median().fillna(0.0).astype(float).to_dict()
    levels = {
        column: frozenset(candidate[column].dropna().astype(str).unique())
        for column in categorical_columns
    }
    # Create a flag for *every original field*, even if it is complete in this
    # training extract.  This makes a new missing state in validation/test
    # visible rather than silently converting it to a median or category.
    source_columns = set(train.columns).difference({ID_COLUMN, TARGET_COLUMN})
    missing_columns = tuple(
        column for column in raw_features
        if column in source_columns or candidate[column].isna().any()
    )
    bin_edges = {
        column: _quantile_edges(candidate[column], n_bins)
        for column in BINNED_FEATURES
        if column in candidate
    }

    provisional = _apply_fitted_processing(prepared, raw_features, medians, levels, missing_columns)
    provisional = _add_fitted_bins(provisional, bin_edges)
    return ApplicationPreparationState(
        raw_feature_columns=raw_features,
        output_feature_columns=tuple(provisional.columns),
        numeric_medians=medians,
        categorical_levels=levels,
        bin_edges=bin_edges,
        missing_indicator_columns=missing_columns,
    )


def transform_application(frame: pd.DataFrame, state: ApplicationPreparationState) -> pd.DataFrame:
    """Transform application rows with an already fitted training state.

    Args:
        frame: Raw train, validation, or test application rows; ``TARGET`` is
            optional and is excluded from the returned matrix.
        state: A state returned by ``fit_application_preparation`` on training data.

    Returns:
        A no-null feature DataFrame with exactly ``state.output_feature_columns``
        in that order and the same row index/order as ``frame``.

    EDA rationale: Q5 required fitting preprocessing once on train and applying
    it unchanged to test despite category, missingness, and distribution shifts.
    """
    validate_application_data(frame)
    prepared = create_application_features(clean_application_values(frame))
    _require_columns(prepared, state.raw_feature_columns)
    transformed = _apply_fitted_processing(
        prepared, state.raw_feature_columns, state.numeric_medians,
        state.categorical_levels, state.missing_indicator_columns,
    )
    transformed = _add_fitted_bins(transformed, state.bin_edges)
    # Reindex is the final safeguard: output schema cannot depend on the input
    # partition, including when a category exists only in test.
    return transformed.reindex(columns=state.output_feature_columns)


def split_features_target(frame: pd.DataFrame, state: ApplicationPreparationState) -> tuple[pd.DataFrame, pd.Series]:
    """Separate a labeled application frame into model features and target.

    Args:
        frame: Labeled raw application data containing ``TARGET``.
        state: Training-fitted preparation state used to build the features.

    Returns:
        A tuple of transformed feature DataFrame and the unchanged ``TARGET``
        Series. ``TARGET`` is never included in the feature matrix (EDA Q3/Q13).
    """
    _require_columns(frame, {TARGET_COLUMN})
    return transform_application(frame, state), frame[TARGET_COLUMN].copy()


def validate_prepared_outputs(
    train_applications: pd.DataFrame,
    test_applications: pd.DataFrame,
    train_features: pd.DataFrame,
    test_features: pd.DataFrame,
) -> dict[str, int | bool]:
    """Verify the required train/test preparation invariants and report them.

    Args:
        train_applications: Original labeled training applications.
        test_applications: Original unlabeled test applications.
        train_features: Output of ``transform_application`` for training rows.
        test_features: Output of ``transform_application`` for test rows.

    Returns:
        A compact report of row counts, shared feature count, null counts, and
        boolean key/schema checks. Raises ``ValueError`` when any invariant fails.

    EDA rationale: Q1 requires unique application keys and Q5 requires a common
    train/test feature schema.  Index and row-count checks ensure transformation
    did not drop, duplicate, or reorder applicants after the key is excluded.
    """
    validate_application_data(train_applications, require_target=True)
    validate_application_data(test_applications)
    if not train_features.columns.equals(test_features.columns):
        raise ValueError("Prepared train and test features do not have identical ordered columns.")
    if len(train_features) != len(train_applications) or len(test_features) != len(test_applications):
        raise ValueError("Preparation changed the number of application rows.")
    if not train_features.index.equals(train_applications.index) or not test_features.index.equals(test_applications.index):
        raise ValueError("Preparation changed application row order/index alignment.")
    train_nulls = int(train_features.isna().sum().sum())
    test_nulls = int(test_features.isna().sum().sum())
    if train_nulls or test_nulls:
        raise ValueError("Prepared feature matrices contain null values.")
    return {
        "train_input_rows": len(train_applications),
        "test_input_rows": len(test_applications),
        "train_feature_rows": len(train_features),
        "test_feature_rows": len(test_features),
        "shared_feature_columns": len(train_features.columns),
        "train_null_values": train_nulls,
        "test_null_values": test_nulls,
        "train_keys_unique": True,
        "test_keys_unique": True,
        "identical_ordered_feature_columns": True,
    }


def join_aggregated_supplementary(
    applications: pd.DataFrame, aggregates: Sequence[pd.DataFrame], *, key: str = ID_COLUMN
) -> pd.DataFrame:
    """Safely left-join already one-row-per-application supplementary aggregates.

    Args:
        applications: Application-level table with one unique row per ``key``.
        aggregates: Timing-audited supplementary tables already aggregated to
            one unique row per application key.
        key: Join key; defaults to ``SK_ID_CURR``.

    Returns:
        ``applications`` left-joined to every aggregate without changing its
        row count. Raises ``ValueError`` instead of allowing duplicate keys or
        column collisions.

    EDA Q14 found no child tables in this workspace, so this module deliberately
    does not fabricate historical aggregations.  When supplied and timing-audited,
    aggregate each child table to one row per ``SK_ID_CURR`` first, then use this
    function.  Duplicate keys fail instead of silently multiplying applications.
    """
    result = applications.copy()
    _require_columns(result, {key})
    for aggregate in aggregates:
        _require_columns(aggregate, {key})
        if aggregate[key].duplicated().any():
            raise ValueError("Each supplementary table must have one row per SK_ID_CURR before joining.")
        overlapping = set(result.columns).intersection(aggregate.columns).difference({key})
        if overlapping:
            raise ValueError(f"Supplementary columns already exist: {sorted(overlapping)}")
        result = result.merge(aggregate, on=key, how="left", validate="one_to_one")
    return result


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide aligned numeric series without creating infinite values.

    Args:
        numerator: Numeric values for the top of a ratio.
        denominator: Numeric values for the bottom of the same ratio.

    Returns:
        Ratio values with zero denominators represented as missing. This supports
        EDA Q8's financial ratios without assigning an artificial extreme value.
    """
    return numerator.div(denominator.mask(denominator.eq(0))).replace([np.inf, -np.inf], np.nan)


def _quantile_edges(series: pd.Series, n_bins: int) -> tuple[float, ...]:
    """Calculate unique training-only quantile edges for one numeric feature.

    Args:
        series: Observed training values for a feature selected in EDA Q8--Q10.
        n_bins: Maximum requested number of equal-frequency bins.

    Returns:
        Ordered numeric bin edges, or an empty tuple if fewer than two distinct
        observed values make binning meaningless.
    """
    observed = series.dropna()
    if observed.nunique() < 2:
        return ()
    edges = np.unique(observed.quantile(np.linspace(0, 1, min(n_bins, observed.nunique()) + 1)).to_numpy())
    return tuple(float(edge) for edge in edges) if len(edges) >= 2 else ()


def _apply_fitted_processing(
    prepared: pd.DataFrame,
    raw_features: Sequence[str],
    numeric_medians: Mapping[str, float],
    categorical_levels: Mapping[str, frozenset[str]],
    missing_indicator_columns: Sequence[str],
) -> pd.DataFrame:
    """Apply fitted imputation, category, and missing-indicator rules.

    Args:
        prepared: Cleaned, feature-created rows to transform.
        raw_features: Ordered feature columns retained before fitted processing.
        numeric_medians: Training-only numeric fill values.
        categorical_levels: Training-only supported levels by categorical field.
        missing_indicator_columns: Fields for which missing-state flags are added.

    Returns:
        A feature DataFrame with explicit missing/unknown categories and no null
        numeric values. This implements EDA Q5/Q6 without fitting on these rows.
    """
    result = prepared.loc[:, raw_features].copy()
    # EDA Q6: preserve a missing-state indicator before filling.  Numeric
    # medians are fitted on train only; categorical missing/unseen values have
    # explicit distinct states, preserving the missingness decision.  Every
    # original application field receives a flag, including all-zero flags in
    # train, so a test-only missing state remains observable.
    missing_flags = pd.DataFrame(
        {
            f"{column}_missing_flag": result[column].isna().astype("int8")
            for column in missing_indicator_columns
        },
        index=result.index,
    )
    result = pd.concat([result, missing_flags], axis=1)
    for column, median in numeric_medians.items():
        result[column] = result[column].fillna(median)
    for column, known_levels in categorical_levels.items():
        values = result[column].astype("string")
        result[column] = values.mask(values.isna(), MISSING_CATEGORY).where(
            values.isna() | values.isin(known_levels), UNKNOWN_CATEGORY
        ).astype("string")
    return result


def _add_fitted_bins(frame: pd.DataFrame, bin_edges: Mapping[str, tuple[float, ...]]) -> pd.DataFrame:
    """Append integer bins using stored training quantile thresholds.

    Args:
        frame: Feature DataFrame after fitted missing-value/category processing.
        bin_edges: Training-derived edges keyed by feature name.

    Returns:
        A copy of ``frame`` with ``*_train_quantile_bin`` columns. Values beyond
        training support are clipped to an outer bin, avoiding a test-only bin.
    """
    result = frame.copy()
    for column, edges in bin_edges.items():
        if not edges:
            continue
        # Integer labels keep this feature compact and avoid an arbitrary order
        # for string interval labels.  Values outside train support fall in the
        # first/last learned bin, rather than producing a test-only category.
        clipped = result[column].clip(lower=edges[0], upper=edges[-1])
        result[f"{column}_train_quantile_bin"] = pd.cut(
            clipped, bins=np.asarray(edges), labels=False, include_lowest=True
        ).astype("float").fillna(-1).astype("int8")
    return result
