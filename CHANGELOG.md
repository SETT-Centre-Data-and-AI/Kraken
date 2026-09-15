## v1.7.2 (2026-09-14)

### Feat

- **graphing**: added ordered x-axis labelling, and expanded set colour scheme

## v1.7.1 (2026-09-10)

### Feat

- **examine**: StatsPack always returned with clean __repr__

### Fix

- **graping_support.py**: fixed new CI binning issue

## v1.6.2 (2026-07-09)

### Fix

- **uploading\support.py**: fixes to prevent breaking of upload when arrays exist within a DataFrame

## v1.7.0 (2026-09-10)

### BREAKING CHANGE

- **graphing**: `graph()` now returns a `GraphResult` instead of `None` or a `DataFrame`. Prepared data is available from `result.data` and the editable Plotly figure from `result.figure`.

### Feat

- **graphing**: add role-aware, all-or-nothing numeric, timedelta, and datetime conversion with suppressible dtype warnings and converted values retained in `GraphResult.data`.
- **graphing**: add a documented `GraphingError` hierarchy for capability, column, dtype, conversion, aggregation, data, rendering, and export failures.
- **graphing**: add a colour-blind-friendly Kraken Plotly theme with humanized labels, concise facets, renderer-specific styling, responsive timeline spacing, and colour-matched regression lines.
- **graphing**: replace static Matplotlib and Seaborn output with responsive interactive Plotly figures and add histogram, timeline, facet, marginal, hover, confidence-interval, and export support.
- **graphing**: add Monday-to-Sunday weekly date aggregation with Monday start-date labels.
- **demo**: package the deterministic synthetic data generator as `kraken.demo` for examples and experimentation.

### Fix

- **graphing**: require quantitative y values for box, violin, density, and scatter graphs instead of plotting categorical distributions in arbitrary order.
- **graphing**: validate aggregation compatibility and x-bin widths, support date and timezone-aware histograms, preserve grouping columns that are reused as measures, and retain box/violin observations when binning x.
- **graphing**: validate timeline null and range rules, fail grouped density plots when any KDE is invalid, and warn when renderer-specific tuning arguments are ignored.
- **graphing**: include `nbformat` as a runtime dependency so Plotly figures render inside supported notebook environments.
- **graphing**: keep confidence-interval error bars visible on white backgrounds and render regression lines above translucent scatter points.
- **graphing**: reorder the shared categorical palette around a higher-contrast blue/orange opening pair that remains distinguishable in scatter plots.
- **graphing**: make scatter regression an explicit opt-in and omit its colour-matched lines from the legend to avoid duplicate group entries.
- **graphing**: stack area-chart colour groups cumulatively instead of drawing overlapping fills from zero.
- **graphing**: render area hover details vertically and order numeric x-axis bins from negative to positive.
- **graphing**: retain empty fixed-width numeric intervals as visible x-axis categories.

## v1.6.2 (2026-07-09)

### Fix

- **uploading/support.py**: fixes to prevent breaking of upload when arrays exist within a DataFrame
- **uploading\support.py**: fixes to prevent breaking of upload when arrays exist within a DataFrame

## v1.6.1 (2026-04-10)

### Feat

- **resync**: resync private and public repos

### Fix

- **sync-from-public.yaml**: fixed to use new centralised orchestrator

## v1.6.0 (2026-03-24)

### Feat

- **workflows**: updated to use centralised CI/CD - fixes to pre-install to follow

### Fix

- **pre-install.sh**: attempt to add additional kraken preinstallation
- **CICD**: fixed sync-to-public (#31)

## v1.5.1 (2026-03-24)

### Feat

- **workflows**: updated to use centralised CI/CD - fixes to pre-install to follow

### Fix

- **pre-install.sh**: attempt to add additional kraken preinstallation
- **CICD**: fixed sync-to-public (#31)

## v1.5.0 (2026-03-05)

### Fix

- **minor-fixes**: various minor fixes

### Refactor

- **connector**: added error check to provide more information on error

## v1.4.0 (2026-03-05)

### Fix

- **sql_execution**: fixed df_name inclusion in mapping causing queries to split under new connectors

## v1.3.0 (2026-02-10)

### Fix

- **sql_execution.py**: Fix execute_sql sort order when the input contains a mix of arraysize and non-arraysize queries. Use defaultdict instead of setdefault as it's faster

### Refactor

- **arraysize**: refactored to include a default
- **__init__.py**: added all functions to __all__ for now
- **support_checks.py**: Refactor _enforce_in_list. This function will never have non-iterables or maps in items arg
- **data_upload.py**: Use isinstance instead of type for type checking
- **graphing.py**: Use isinstance instead of type for type checking. Fix some type hints
- **progress.py**: Use support.is_notebook instead of __is_jupyter. Fix some type hints
- **support.py**: Update is_notebook function. Update _check_filetype type hints

## v1.2.3 (2025-11-27)

### Feat

- **pyproject.toml**: turned on auto changelog

## v1.2.2 (2025-11-27)

### Fix

- **changelog.md**: tweak to trigger bump

## v1.2.1 (2025-11-27)

### Feat

- **initial-commit**: initial commit

### Fix

- **actions**: fixed smoke test (#6)
