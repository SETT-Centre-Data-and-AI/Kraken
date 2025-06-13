<p align="center">
  <img src="docs/images/kraken.png" alt="Kraken", width=300>
</p>

# Kraken
Kraken is a convenience package that orchestrates data extraction by integrating SQL with Python, while managing safe storage and recall of sensitive connection credentials.

Developed in the NHS at University Hospital Southampton to facilitate clinical research in a complex multi-database environment, Kraken provides streamlined management of Reproducible Analytical Pipelines (RAPs) from multiple data sources by automating extraction, parsing, connection and execution of SQL files. Offering multiple levels of control, Kraken can run an entire SQL data pipeline from extraction to export with as little as one line of Python code, or provide more fine-tuned management of entire ETL flows through use of underlying connector objects. Kraken also provides standardised statistical summaries and graphing for speedy interrogation of results.

Wrapping around packages like `keyring`, `sqlalchemy`, `pyodbc`, `pandas`, `matplotlib` and `seaborn`, Kraken:
* Safely stores sensitive database connection credentials under an 'alias' in your operating system's credential store, and recalls them on demand and as dictated by SQL files;
* Extracts all SQL from a targeted file or folder of files (sequentially or simultaneously) - parsing and splitting them into queries before executing them in order;
* Returns DataFrame results that include provenance metadata for auditable tracking;
* Allows database upload of data with fine-tuned control;
* Integrates extraction of local data files;
* Provides fast data interrogation with single-line graphing and statistical summary functions.

# Guides
* [Installation and Setup Guide](./docs/installation-and-setup-guide.md)
* [Usage Guide](./docs/usage-guide.md)

# Quickstart Example
```
pip install data-kraken
```

```py
import kraken

# Set default database alias (once)
kraken.set_default_alias("TEST")

# Save test connection (once)
kraken.save_connection_MSSQL(alias="TEST", server="xxx", database="xxx", username=None, password=None, default=True)

# Execute SQL file in folder
results = kraken.run(filepaths='sql_folder')

# Examine summary statistics
for result in results:
    result.examine()
```

# Function Quick List
#### Connection
- `save_connection()` - save database service credentials to OS's credential manager under an alias for recall
- `save_connection_XXX()` - convenience wrapper around `save_connection()` for various supported database platforms
- `execute()` - execute SQL query
- `create_connector()` - create Connector object to reuse for SQL execution

#### SQL Execution
- `extract_sql()` - extract & parse SQL files from provided filepath, preparing collection of queries
- `execute_sql()` - execute collection of queries from `extract_sql()`
- `export()` - export results to various filetypes
- `run()` - wrapper around above functions, allowing extraction, execution, and optional export results from SQL files

#### Data Import
- `extract_spreadsheets()` - extract data from spreadsheets

#### Data Upload
 - `upload()` - upload single DataFrame to database (note that this always commits)
 - `upload_results()` - upload collection of DataFrames to database (note that this always commits)

#### Analysis
- `examine()` - analyse DataFrame & provide high-level statistical summary
- `graph()` - graph DataFrame quickly with support for multiple graph types

#### Helpers
- `generate_where_clause()` - loop over a DataFrame to convert rows or columns into batches of WHERE clauses
- `datestamp()` - get current time or datestamp as a string with formatting options
- `calculate_runtime()` - get timedelta and formatted string between two datetime values
- `readout.activate()/suppress()` - turn readout on or off
- `encode()`/`decode()` - convenient wrappers around keyring to store/recall secrets

# Class Object Quick List
- `Connector` (use `create_connector`) - object allowing fine-tuned SQL connection & execution control
- `Parser` - object allowing SQL parsing (as used in `extract_sql()`)
- `Progress` - heavily customisable progress bar/ticker with threaded auto-refresh and context management

# Supported Database Platforms
These database platforms are currently supported:
 - Oracle
 - Microsoft SQL Server
 - PostgreSQL
 - MySQL
 - MariaDB
 - IBM Informix
 - Intersystems Cache
 - Intersystems Iris

# Future Development
What we're working on next:
 - Integration with BitWarden for credential storage
 - Direct import/export to Microsoft SharePoint
 - Pipeline execution logging and run reports
 - Expanded database platform support

# Contributing
Interested in contributing? Check out the contributing guidelines. Please note that this project is released with a Code of Conduct. By contributing to this project, you agree to abide by its terms.

# License
This work is licensed under a
[Creative Commons Attribution-NonCommercial 4.0 International License][cc-by-nc].
[![CC BY-NC 4.0][cc-by-nc-shield]][cc-by-nc]

[cc-by-nc]: https://creativecommons.org/licenses/by-nc/4.0/
[cc-by-nc-shield]: https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg
[SETT]: https://github.com/SETT-Centre-Data-and-AI

# Authors
Kraken was developed within the NHS by Cai Davis, Michael George, and Faizan Hemotra at University Hospital Southampton NHSFT, as part of the [Southampton Emerging Therapies and Technology (SETT) Centre][SETT].
<p align="center">
  <a href="https://github.com/SETT-Centre-Data-and-AI">
    <img src="docs/images/SETT Header.png" alt="NHS UHS SETT Centre">
  </a>
</p>
