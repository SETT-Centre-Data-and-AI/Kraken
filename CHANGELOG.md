## v1.2.0
### Fix

- **ubuntu**: refactored kraken for ubuntu compatibility
- **oracle**: added arraysize support for oracle to speed up SQL execution

## v1.1.8 (2025-08-19)

### Feat

- **rebump**: rebump
- **rebump**: rebump

## v1.1.7 (2025-08-19)

### Feat

- **datakraken**: changed slug to datakraken

## v1.1.6 (2025-08-01)

### Feat

- **connector**: refactored df processing on download to allow for more accurate progress reporting

## v1.1.5 (2025-07-22)

### Refactor

- **pyproject.toml**: attempt to get cz bump working

## v1.1.4 (2025-07-22)

### Refactor

- **pyproject.toml**: attempt to get cz bump working

## v1.1.4 (2025-07-22)

### Fix

- dummy commit to bump patch version

### Refactor

- **version**: set 1.1.3 in attempt to align tags and cz

## v1.1.3 (2025-07-22)

### Feat

- **version**: 1.1.0

### Fix

- **Connector**: added try/except block to prevent drivers like psycopg2 failing on nextset()

## v1.0.1 (2025-07-18)

### Feat

- **pyproject.toml**: turned off major_version_zero = true
- **sql_extraction**: isolation_level flag supports 'isolation_level' and 'isolationlevel'
- **ribosome**: added configuratble isolation_level for SQL extraction and execution, and --$Isolation_level support
- **connector.py**: added configurable isolation_level on Connector instantiation
- **github**: reimporting published package
- **initial-commit**: initial commit

### Fix

- **sql-encoding**: added encoding="utf-8" to fix issue reading certain unicode characters - GitHub#1
