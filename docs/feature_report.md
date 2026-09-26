# Thin-file repayment-risk feature report

## Scope and method

This report identifies feature families that consumer lenders use, or disclose
using, when assessing repayment risk where conventional bureau information is
limited. It then maps each family to the data documented in
[`data_map.md`](data_map.md). No values, rates, aggregates, or model results
were computed.

**Availability labels**

- **Build now** — can be derived using only `application_train.csv` and/or
  `application_test.csv`.
- **Partial / proxy only** — an application-level approximation is available,
  but it is not the full underwriting concept.
- **Documented but unavailable** — the data dictionary names the fields and
  table, but that table is not present in this project.
- **Not available** — neither the necessary fields nor a source table are
  documented in this project.

For compactness, `application_*.csv` below means the identically named column
in **both** `application_train.csv` and `application_test.csv`; the sole
schema exception is `TARGET`, which exists only in `application_train.csv`.

## Evidence base

1. Upstart's 2024 Form 10-K says its personal-loan model uses variables
   related to credit experience, employment, educational history, bank-account
   transactions, cost of living, and loan-application interactions. It also
   says lending partners may apply minimum credit-score, loan-amount, and
   debt-to-income (DTI) requirements before model scoring. [Upstart Holdings,
   Inc., 2024 Form 10-K (filed 2025-02-14)](https://www.sec.gov/Archives/edgar/data/1647639/000164763925000018/upst-20241231.htm)
   (`S1`).
2. Berg, Burg, Gombović, and Puri show that digital-footprint information can
   predict consumer credit risk and is particularly valuable when conventional
   credit-bureau information is limited. Their examples concern online
   interaction/device information, not just a declared application field.
   [“On the Rise of FinTechs: Credit Scoring Using Digital Footprints,” *The
   Review of Financial Studies*, 2020](https://doi.org/10.1093/rfs/hhz099)
   (`S2`).
3. The CFPB's Regulation B rule prohibits use of prohibited bases in a credit
   evaluation system and sets limits on age-related treatment. [12 CFR
   § 1002.6](https://www.consumerfinance.gov/rules-policy/regulations/1002/6/)
   (`S3`).
4. Regulation B also requires adverse-action notifications and specific
   reasons, which makes feature definitions, lineage, and reason-code support
   a production requirement rather than a modeling afterthought. [12 CFR
   § 1002.9](https://www.consumerfinance.gov/rules-policy/regulations/1002/9/)
   (`S4`).

`S1` is evidence of a lender's disclosed practice, not a claim that every
lender uses every feature below. `S3` and `S4` are U.S. regulatory guardrails,
not legal advice.

## Feature-to-data mapping

| Underwriting feature family | Why it is relevant to thin-file lending | Can this project build it? Exact columns and tables | Limitations / implementation guardrails |
| --- | --- | --- | --- |
| **Credit experience and repayment history** | Conventional credit experience is a core disclosed model-input family (`S1`). For a thin file, even limited prior trade-line status or payment history can be informative. | **Documented but unavailable.** The dictionary describes `bureau.csv`: `SK_ID_CURR`, `CREDIT_ACTIVE`, `DAYS_CREDIT`, `CREDIT_DAY_OVERDUE`, `DAYS_CREDIT_ENDDATE`, `DAYS_ENDDATE_FACT`, `AMT_CREDIT_SUM`, `AMT_CREDIT_SUM_DEBT`, `AMT_CREDIT_SUM_OVERDUE`, and related trade-line fields. It also describes `bureau_balance.csv`: `SK_BUREAU_ID`, `MONTHS_BALANCE`, `STATUS`; and `installments_payments.csv`: `SK_ID_CURR`, `SK_ID_PREV`, `DAYS_INSTALMENT`, `DAYS_ENTRY_PAYMENT`, `AMT_INSTALMENT`, `AMT_PAYMENT`. None of these tables is present. | Do not substitute `TARGET` for prior repayment history; it is the outcome. Join available child data to applications on `SK_ID_CURR` only after aggregating it to one row per current application. |
| **Outstanding debt, credit limits, and utilization** | Debt burden and credit experience are disclosed components of lender underwriting (`S1`). | **Documented but unavailable.** `bureau.csv` provides `AMT_CREDIT_SUM`, `AMT_CREDIT_SUM_DEBT`, and `AMT_CREDIT_SUM_LIMIT`; `credit_card_balance.csv` provides `SK_ID_CURR`, `SK_ID_PREV`, `AMT_BALANCE`, `AMT_CREDIT_LIMIT_ACTUAL`, and receivable/balance fields. Neither table is supplied. | `application_*.csv.AMT_CREDIT` is the requested/current loan amount, not an existing revolving balance or credit limit; it cannot create utilization. |
| **Recent credit enquiries** | The lender disclosure identifies credit experience (`S1`); recent applications/enquiries are a limited bureau-signal component. | **Build now, but limited.** In both `application_train.csv` and `application_test.csv`, use `AMT_REQ_CREDIT_BUREAU_HOUR`, `AMT_REQ_CREDIT_BUREAU_DAY`, `AMT_REQ_CREDIT_BUREAU_WEEK`, `AMT_REQ_CREDIT_BUREAU_MON`, `AMT_REQ_CREDIT_BUREAU_QRT`, and `AMT_REQ_CREDIT_BUREAU_YEAR`. | These are count fields with missing values. They provide no enquiry type, lender, amount, or full trade-line context. Preserve missingness rather than assuming zero. |
| **Income and capacity to pay** | Income is a disclosed input family and DTI is a disclosed lender policy gate (`S1`). | **Build now for stated income and a payment-to-income proxy.** `application_*.csv`: `AMT_INCOME_TOTAL`; current-loan terms `AMT_ANNUITY`, `AMT_CREDIT`, `AMT_GOODS_PRICE`, and `NAME_CONTRACT_TYPE`. Examples of *candidate definitions* are stated income and requested-payment-to-income; no calculation is performed here. | This is not verified income and not full DTI. The project has no recurring-debt-payment total, tax/benefit data, paystub, or bank-deposit feed. Treat an annuity-to-income ratio as a requested-loan burden proxy only. |
| **Employment stability and occupation** | Employment is a disclosed model-input family (`S1`) and supplies repayment-capacity context when bureau depth is limited. | **Build now, conditionally.** `application_*.csv`: `DAYS_EMPLOYED`, `NAME_INCOME_TYPE`, `OCCUPATION_TYPE`, `ORGANIZATION_TYPE`, and `AMT_INCOME_TOTAL`. | Convert the known `DAYS_EMPLOYED = 365243` sentinel to missing/unknown and retain a sentinel indicator if approved. This is self/application data; it is not employment verification. |
| **Education history** | Educational history is explicitly disclosed as a model-variable family (`S1`). | **Partial.** `application_*.csv.NAME_EDUCATION_TYPE` can represent highest declared education level. | The data has no institution, degree field, course of study, credential verification, or completion date. Any use needs fair-lending, explainability, and policy review. |
| **Loan request characteristics** | Loan amount and application interactions are disclosed inputs/policy controls (`S1`). | **Partial.** `application_*.csv`: `NAME_CONTRACT_TYPE`, `AMT_CREDIT`, `AMT_ANNUITY`, `AMT_GOODS_PRICE`, `WEEKDAY_APPR_PROCESS_START`, and `HOUR_APPR_PROCESS_START`. | The current-application table has no stated loan purpose, APR, original term, channel, clickstream, or application revision history. Time-of-submission is not a substitute for full interaction telemetry. |
| **Bank-account cash flow, deposits, and expense volatility** | Bank-account transactions are explicitly named in the lender disclosure (`S1`), and can help when a bureau file is thin. | **Not available.** No table contains account balances, deposits, transactions, recurring expenses, overdrafts, NSF events, or account tenure. | Historical loan-payment tables, if later provided, are not consumer deposit-account transaction feeds and should not be described as cash-flow underwriting data. |
| **Alternative payment history (rent, utilities, telecom)** | This is a common thin-file concept: recurring non-loan payment evidence can supplement sparse conventional credit data. It is distinct from the bank-transaction family disclosed in `S1`. | **Not available.** No documented table or column identifies rent, utility, mobile, broadband, insurance, or landlord payment performance. `FLAG_PHONE`, `FLAG_MOBIL`, and `FLAG_EMAIL` only record contact availability, not payment history. | Do not infer payment performance from contact flags, housing type, or address data. Any future alternative-data source needs consent, permissible-purpose, data-quality, and fair-lending review. |
| **Housing and residential/contact stability** | Residence stability and cost-of-living context can be used as capacity or continuity signals; `S1` specifically discloses cost-of-living variables. | **Partial / proxy only.** `application_*.csv`: `NAME_HOUSING_TYPE`, `DAYS_REGISTRATION`, `DAYS_LAST_PHONE_CHANGE`, `REGION_POPULATION_RELATIVE`, `REGION_RATING_CLIENT`, `REGION_RATING_CLIENT_W_CITY`, `REG_REGION_NOT_LIVE_REGION`, `REG_REGION_NOT_WORK_REGION`, `LIVE_REGION_NOT_WORK_REGION`, `REG_CITY_NOT_LIVE_CITY`, `REG_CITY_NOT_WORK_CITY`, `LIVE_CITY_NOT_WORK_CITY`, `TOTALAREA_MODE`, `HOUSETYPE_MODE`, `WALLSMATERIAL_MODE`, and `EMERGENCYSTATE_MODE`. | There is no address, ZIP/postcode, rent amount, housing-payment history, local price index, or verified tenure. Regional fields can be geographic proxies; require heightened fair-lending/redlining review. The test rating value `-1` is a documented dictionary exception. |
| **Household/dependent obligations** | Household composition may help describe stated obligations, but it is not a substitute for verified expenses. | **Partial.** `application_*.csv`: `CNT_CHILDREN`, `CNT_FAM_MEMBERS`, and `NAME_FAMILY_STATUS`. | `NAME_FAMILY_STATUS` can encode marital-status information. Under `S3`, it must not be used as a prohibited-basis risk input. Counts are self-reported and no household income, alimony, child-support, or expense data is present. |
| **Application fraud and identity/contact verification risk** | The lender disclosure says its models address income and identity fraud and loan stacking (`S1`). | **Partial.** `application_*.csv`: `FLAG_DOCUMENT_2`–`FLAG_DOCUMENT_21`, `FLAG_MOBIL`, `FLAG_EMP_PHONE`, `FLAG_WORK_PHONE`, `FLAG_CONT_MOBILE`, `FLAG_PHONE`, `FLAG_EMAIL`, address-mismatch flags, `DAYS_ID_PUBLISH`, and `DAYS_LAST_PHONE_CHANGE`. | These fields indicate provided documents/contact attributes or changes; they do not confirm identity, detect synthetic identity, verify income, detect device reuse, or identify cross-application stacking. Avoid labeling a raw document flag as “fraud” without validated outcome and governance. |
| **Digital footprint and online application behavior** | Peer-reviewed evidence shows digital-footprint information can add predictive value where bureau information is sparse (`S2`); the lender disclosure also names application interactions (`S1`). | **Partial, very weak proxy only.** `application_*.csv.WEEKDAY_APPR_PROCESS_START` and `HOUR_APPR_PROCESS_START` record submission timing. | No device type, operating system, browser, IP, geolocation, email-domain metadata, clickstream, typing, session, referral, or application-path data exists. Do not call the two time fields a digital footprint. |
| **External risk scores** | Third-party scores can supplement limited lender-held information. | **Partial but opaque.** `application_*.csv`: `EXT_SOURCE_1`, `EXT_SOURCE_2`, and `EXT_SOURCE_3`. | The dictionary calls these normalized external scores but gives no provider, permitted use, score construction, reason codes, refresh date, or consent/provenance. They require vendor governance and explainability review before use. |
| **Protected characteristics and prohibited-basis proxies** | These must be controlled rather than treated as ordinary repayment-risk features. Regulation B restricts use of prohibited bases and age treatment (`S3`); adverse-action requirements require explainable, defensible decisions (`S4`). | **Do not build as ordinary risk features.** `application_*.csv.CODE_GENDER`; `NAME_FAMILY_STATUS`; and `DAYS_BIRTH` (age). Geographic fields listed in the housing row are potential proxy variables requiring review. | Keep these fields out of a standard repayment-risk feature set unless a documented legal/compliance purpose authorizes their collection/use (for example, monitoring). This report does not decide legal permissibility. |

## Practical implication for this project

With only the two supplied application files, the strongest build-now families
are stated income/payment burden, employment context, limited enquiry counts,
declared education, application request attributes, housing/contact proxies,
document/contact signals, and opaque external scores. The data **cannot**
currently build the most important thin-file supplements—bank cash flow,
alternative payment histories, device/behavioral digital footprints, verified
identity/income, or the dictionary-described credit-bureau and historical
repayment features—because the required source tables are absent.

Before any model is built, define approved feature definitions, time of
availability, missing-value handling, fair-lending review, and adverse-action
reason support. In particular, exclude `TARGET` and `SK_ID_CURR` from features
and treat `DAYS_EMPLOYED = 365243` as the documented sentinel rather than a
literal employment duration.
