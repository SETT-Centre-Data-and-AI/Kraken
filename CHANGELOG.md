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
