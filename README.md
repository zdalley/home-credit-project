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
