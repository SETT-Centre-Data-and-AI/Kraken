# Installation & Setup Guide
## Contents
- [Installation](#installation)
- [Setup](#setup)
    - [Set Kraken Defaults](#set_kraken_defaults)
    - [Save Database(s)](#save_databases)

# Installation<a id="installation"></a>
### Via PyPI
Execute:
```
pip install datakraken
```

### Via GitHub
To install in development mode, we recommend using poetry. Execute:
```
pip install poetry
```

Clone the repo:
```
git clone https://github.com/SETT-Centre-Data-and-AI/Kraken.git
```

Navigate to the repositry (`cd ...\Kraken\`) and execute
```
poetry install
```

# Setup<a id="setup"></a>
## Set Kraken Defaults<a id="set_kraken_defaults"></a>
Kraken uses `keyring` to facilitate secure storage and recall of database credentials in your machine's credential manager for ease of access, rather than storing this sensitive information itself. This feature is leveraged to store a few other default settings/fallbacks too, so the first thing you'll want to do is set this up. This should only need to be run once per machine (unless you wish to change a default variable):
 1. Open a new python file or Jupyter Notebook.
 2. Run `import kraken`
 3. Run `kraken.set_kraken_defaults()`
 4. Complete the prompts for input. These default variables are:
     - `default_database` _(database alias for Kraken to use as a default when the alias database is not specified within a SQL query; note: in this guide we will use "RESEARCH" but feel free to tweak yours, and the forthcoming code, accordingly)_
     - `oracle_client`: _(directory location of 64-bit Oracle `oci.dll` and `oraociei.dll` drivers to be utilised for `oracledb` Oracle connections)_

## Save Database(s)<a id="save_databases"></a>
Kraken allows the saving and retrieval of database connections in the local Credential Manager. Each connection is saved with an `alias`, which Kraken can then interpret from both user input and SQL files to query specific database services. A database can be saved multiple times with different usernames, but a `username`/`alias` pair must be unique, and only one can pair can be assigned as a default _(allowing connection with a particular username without having to specify it)_.

For convenience, a number of database platforms include convenience functions to save having to construct connection strings yourself. These include:
 - `kraken.save_connection_MSSQL()`
 - `kraken.save_connection_Oracle()`
 - `kraken.save_connection_Informix()`
 - `kraken.save_connection_Cache()`
 - `kraken.save_connection_MariaDB()`
 - `kraken.save_connection_PostgreSQL()`
 - `kraken.save_connection_MySQL()`
 - `kraken.save_connection_Iris()`


Alternatively, a `pyodbc`/`sqlalchemy` supported connection url string can be specified and saved using:
 - `kraken.save_connection()`

In all instances, adding the argument `default=True` stores this `username`/`alias` pair as a fallback default for that database `alias` - meaning the username does not have to be later specified each time SQL is executed. We recommend ensuring that a default username is set for each `alias` saved, as this is necessary for SQL file execution.

When initially saving, Kraken will first attempt to connect, and request confirmation to save should this fail (unless overridden with `autosave = True`).

```python
# Example
import kraken
kraken.save_connection_MSSQL(
    alias="RESEARCH",
    server="localhost",
    database="master",
    username=None, # MSSQL can be saved with username=None to use Windows Authentication
    password=None,
    default=True,
    driver_version=17,
    trust_server_certificate=True,
)
```
