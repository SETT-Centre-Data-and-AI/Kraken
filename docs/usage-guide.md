# Usage Guide
The following examples will use a Jupyter Notebook, imaginary SQL, and a MSSQL database saved by using `alias="RESEARCH"` with `kraken.save_connection_MSSQL()`. Please adapt your own code accordingly.

## Contents
 - [Executing SQL Directly](#executing_sql_directly)
 - [Executing SQL Files & Exporting Results](#executing_sql_files)
 - [Executing SQL Files Without Splitting Queries](#executing_without_splitting)
 - [Setting Isolation Level](#setting_isolation_level)
 - [Inspecting DataFrames](#inspecting_dataframes)
 - [Running the Ribosome](#running_ribosome)
 - [Extracting Spreadsheets](#extracting_spreadsheets)
 - [Uploading DataFrames](#uploading_dataframes)
 - [Readouts](#readouts)
 - [Stats & Graphing](#stats_and_graphing)

## Save Database(s)
See [Installation and Setup Guide](./installation-and-setup-guide.md) to save database connections.

## Executing SQL Directly <a id="executing_sql_directly"></a>
### Quick Execution
Firstly, try executing some SQL directly against your saved database using `kraken.execute()`. For example:
```python
import kraken
df = kraken.execute(alias="RESEARCH", query="SELECT TOP 100 * FROM patients")
display(df.head())
```
In this example, Kraken uses the connection credentials saved for the database alias 'RESEARCH' to connect to the database, execute the query, and return results as a DataFrame. We have not provided a `username`, so Kraken will use the default saved for this alias as long as `default=True` was used when saving the connection. To specify a username (if you have multiple saved under the same `alias`), you can use the `username` argument.

When using `kraken.execute()`, Kraken:
1) Instantiates a `Connector` object
2) Connects to the database
3) Executes the query
4) Fetches the resultant data
5) Creates a `DataFrame`
6) Closes the connection

### Reusing a Connector
While using `kraken.execute()` in the manner above can be the simplest method of quickly executing a single query, you may wish to optimise the execution of a multiple queries by avoiding creating and close a new connection in each case. To do this, we can first instantiate a Kraken `Connector` object, and then use it to execute queries with fine-tuned control.

For example:
```python
connector = kraken.create_connector(alias="RESEARCH", autoclose=False)

connector.connect()

patients = kraken.execute("SELECT * FROM patients")
tests = kraken.execute("SELECT * FROM blood_tests")

connector.close_connection()
```

Here, instantiating a `Connector` with `autoclose=False` leaves the connection open after each query execution - and we close it manually when we're finished. This can also be controlled within the `execute()` function with the `close` argument. We also opened a new connection manually with `connect()` before executing SQL, but `execute()` will automatically establish a connection itself if one is not already open.

Direct control of `Connector` objects allows for optimised querying across databases where Linked Servers cannot be used:
```py
from pandas import concat

# Set up connections
epr = kraken.create_connector("EPR")
lab = kraken.create_connector("PATHOLOGY", autoclose=False)

# Identify patients
patients = epr.execute("SELECT TOP 10 patient_no FROM patients")

# Loop over each patient in another database
test_result_dfs = []
for patient_no in patients['patient_no'].unique():
    df = lab.execute(query=f"""
                SELECT  *
                FROM    blood_tests
                WHERE   1=1
                    AND patient_no = '{patient_no}'
                    """,
                progress=False,
                commit=False) # Turn off commit and progress feedback to increase speed

    if not df.empty:
        test_result_dfs.append(df)

# Clean Up
lab.close_connection()
results = concat(test_result_dfs)
display(results)
```

## Executing SQL Files & Exporting Results <a id="executing_sql_files"></a>
Kraken can also read and execute SQL files. To do so, it reads comment flags within the SQL to identify which database to use (`$Database`), and what to name the resulting DataFrame (`$Dataframe`). These are, however, optional, and Kraken will revert to defaults if no flags are entered. To test this, let's create a folder called `sql_folder` in the directory with our notebook, and write a few SQL files:

1. test_01.sql =
    ```sql
    --$Database = RESEARCH
    --$Dataframe = Pathology
    SELECT TOP 100 * FROM blood_tests
    ;

    --$Dataframe = Diagnoses
    SELECT TOP 100 * FROM icd_diagnoses
    ;
    ```

2. test_02.sql =
    ```sql
    --$Database = PHARMACY
    SELECT TOP 100 * FROM prescriptions WHERE ROWNUM <= 100
    ```

_Note that one `$Database` flag is used per file, whereas multiple `$Dataframe` flags can be included within each query. Flags are not case sensitive. If `$Dataframe` flags are ommitted, Kraken will name queries based on the filename. Including `$Dataframe` flags is useful for being able to call specific DataFrame objects from the results downstream, monitoring execution progress, and for flowing through into filenames for exported files. They can be used regardless of whether a query will actually return data._

With this setup, we can test three functions:
 - `extract_sql()` _- takes a filepath to a file or directory (or a list thereof), and extracts and parses all SQL to return a list of `Query` objects in a `QueryList`._
 - `execute_sql()` _- takes the list of `Query` objects returned from the above, and execute them against the relevant databases, returning results as a list of `Result` objects in a `ResultList`._
 - `export_results()` _- takes this list of `Result` objects (or a single one, or a DataFrame), and exports to supported filetypes (.csv/.xlsx)_

With this in mind, let's execute our sql and export results. Bear in mind that Kraken accepts relative file paths, so with these files sitting within a subfolder called 'sql_folder':

```python
sql_path = "sql_folder"
export_path = "export_folder"

queries = kraken.extract_sql(filepaths=sql_path)
results = kraken.execute_sql(query_list=queries)
exports = kraken.export_results(results=results, directory=export_path)
exports = kraken.export_results(results=results, directory=export_path, extension="xlsx")
```
Kraken will execute files in alphabetically order, but this can be manually controlled by passing in a list of folder or filepaths in a specific order, like: `filepaths=['sql_folder/test_02.sql', 'sql_folder/test_01.sql']` (note that a single file can be included multiple times in a list).

Files can be run simultaneously in separate threads rather than sequentially by passing `concurrent=True` to `execute_sql()`. Note that queries *within* the files will still be executed sequntially, but each file will be run at the same time.

During export, a folder called `export_folder` has been created, and contains three .csv files and a single .xlsx file. The .csv filenames are named using the `--$Dataframe` flags provided, with the execption of the third where we did not provide one. Notice how this therefore falls back to the name of the SQL file instead.

The .xlsx file is assigned a name based on the first dataframe, and the sheets within are named similarly to the .csv files. When exporting with `extension='xlsx'`, the `filename` argument can also be provided to name the output file, while the sheet names will remain automatically derived from the initial `--$Dataframe` flags.

It is worth spending some time exploring the other arguments in this function. The arguments `prefix` and `suffix` can be used to tweak the filenames when using a filetype extension that writes DataFrames to multiple files rather than just one (like csv or parquet), and `zip_filename` will zip all files in memory before writing. Using `overwrite=True` allows overwriting existing files, otherwise Kraken will append the new file with a number ('_01', '_02', ...) in a conflict.

## Executing SQL Files Without Splitting Queries <a id="executing_without_splitting"></a>
Kraken will, by default, parse and split queries within files, and then manage the execution of each one by one. This allows each to be assigned a `df_name` (using the `--$dataframe` flag), and each query's progress to be individually monitored. However in some cases (e.g. in more complex/procedural Microsoft SQL Server queries), this behaviour may not be preferable.

For example, using MSSQL declarations requires an entire script to be executed within a single context. In this case the flag `--$Split=False` can be used within the SQL file to stop Kraken from executing queries separately. Kraken will still return multiple DataFrames if applicable.

Note two important points:
 - this behaviour will only work if the database platform itself supports it (e.g. this will not not work with Oracle databases).
 - because Kraken is not splitting queries, assigning names, and then executing them one by one - only a single `--$Dataframe` flag can be assigned (with any returned DataFrames being assigned numbering accordingly). If multiple such flags are detected when not splitting queries, Kraken will use the last and continue, but warn the user.
 - the last `--$Dataframe` flag will be used for naming.

## Setting Isolation Level <a id="setting_isolation_level"></a>
By default, all connections will set an isolation level according to database/driver defaults. If the isolation level needs to be controlled, the `--$Isolation_level` flag can be used in a SQL file (underscore is optional). Alternatively, the `isolation_level` argument can be passed to:
 - `run()`
 - `execute_sql()`
 - `create_connector()`

For example if experiencing errors like 'operation cannot be performed within a transaction', `--$Isolation_level=AUTOCOMMIT` (SQL) or `isolation_level='AUTOCOMMIT'` (argument) could be used. This behaviour will only work for SQL Alchemy driven connections. If used in BOTH the SQL File (flag) and in `run()` or `execute_sql()` (passed as arguments), the latter will override the former.

When used at the `Connector` level, commit behaviour may not be controlled with `commit()` and `rollback()`, depending on the isolation level chosen.

Here's an example using a Microsoft Azure Synapse SQL Data Warehouse that would fail without specifying the isolation level:

```sql
--$Database = BEDROCKDEV
--$Dataframe = CreateTestTable
--$Split=FALSE
--$IsolationLevel=AUTOCOMMIT

IF OBJECT_ID('rds.test_table') IS NOT NULL
    DROP TABLE rds.test_table;
;

IF OBJECT_ID('rds.test_table', N'U') IS NULL
BEGIN

    CREATE TABLE test_table
    (
        id INT NOT NULL,
        name NVARCHAR(100),
        created_at DATETIME
    )
    WITH
    (
        DISTRIBUTION = ROUND_ROBIN,
        CLUSTERED INDEX
        (
            [id] ASC
        )
    )

END

IF OBJECT_ID('rds.test_table') IS NOT NULL
    DROP TABLE rds.test_table;
;
```

## Inspecting DataFrames<a id="inspecting_dataframes"></a>

The `results` variable we defined in the previous block is a list of the results from the SQL queries, and each is a special class called a `Result`. This allows elements of the individual `Result` objects to be inspected by calling their index and element names:
```python
path_name = results[0].df_name
diag_df = results[1].df

print(f"This is the name of the pathology dataframe: '{path_name}'\n")
print(f"This is the result of the diagnosis query:")
display(diag_df.head())
```

Moreover, because the `results` variable containing each of these `Result` objects is a `ResultList`, we can in fact pluck out DataFrames by calling the original `--$dataframe` flag names themselves and using the `get` function:
```python
path = results.get("Pathology")

print(f"""The '{path.df_name}' dataframe was retrieved from the SQL file '{path.filename}' with the following SQL:
{path.sql}
""")

print(f" - and here is the result:")
display(path.df.head())
```

Note that because the `get` function unpacks the elements of the `Result`, you can edit these in place. For example, you can use `get` to extract a DataFrame, edit it in place, and export the `results` object (`kraken.export_results(results)`) with your changes made:

```py
path = results.get('Pathology')
path.df_name = 'BloodTests'

kraken.export_results(
    results=None,
    directory="export_folder",
    prefix=f"{kraken.datestamp()}_",
    extension="csv",
    overwrite=False,
)
```

## Running the 'Ribosome' (single-line control)<a id="running_ribosome"></a>
The three functions explored are brought together in a single wrapper function: `run()`. Kraken extracts all SQL files from input filepaths via the argument `filepaths`, and, if `export_filepaths` is entered, will export the results. If no `filepaths` argument is given and the script is run from an `.ipynb` Jupyter Notebook, the ribosome will look in the directory of the notebook for SQL files. To replicate this behaviour in a .py file, simply pass `filepaths=''`.

Let's run all this with a single line:

```python
results = kraken.run(
    filepaths='sql_folder',
    export_directory="export_folder",
    export_extension="xlsx",
    export_filename="All Data Exports",
)
```

When exporting, note the overwrite warning and renaming behaviour if you run this code block again. Take a look at the `export_overwrite` argument to check out alternative behaviour.

These functions can take a number of arguments worth experimenting with.

## Extracting Spreadsheets<a id="extracting_spreadsheets"></a>
Similarly, Kraken can also extract .csv or .xlsx files directly into `Result` objects in a `ResultList`, as per SQL query outputs. Let's extract everything that we just exported:
```python
imports = kraken.extract_spreadsheets(filepaths="export_folder")
```

The resulting `imports` can be manipulated as previously outlined for `ResultList` and `Result` objects.

## Uploading DataFrames<a id="uploading_dataframes"></a>
Kraken can also upload data to databases:

```python
# First, let's grab a dataframe from earlier on:
data_to_upload = results.get("Diagnoses").df

# Now, let's upload it:
kraken.upload("RESEARCH", df = data_to_upload, schema="dbo", table="KRAKEN_UPLOAD_TEST")
```

Try to run that again, and you'll see that an kraken recognises a conflict because the table already exists and asks you what to do, with a few options provided.

To set automatic overwrite behaviour, you can use the `if_table_exists` argument with 'DROP', 'REPLACE', or 'APPEND'.

```python
# First, let's grab a dataframe from earlier on:
data_to_upload = results.get("Diagnoses").df

# Now, let's upload it with auto-overwrite behaviour:
kraken.upload(
    "RESEARCH",
    df=data_to_upload,
    schema="dbo",
    table="KRAKEN_UPLOAD_TEST",
    if_table_exists="append",
)
```

If a database service supports multiple database (such as SQL Server, where the structure within a service is `database.schema.table`), you can append the database name to the schema to upload. For example:

```python
# First, let's grab a dataframe from earlier on:
data_to_upload = results.get("Pathology").df

# Now, let's upload it, specifying a particular datbase:
kraken.upload(
    "RESEARCH", df=data_to_upload, schema="testing.dbo", table="KRAKEN_UPLOAD_TEST"
)
```

**IMPORTANT**
Note that Kraken will always commit immediately upon data upload. This applies even when using `connector.upload()` with an existing Connector object, and even when the connector's `autocommit` behaviour is set to `False`. This is because the connector uses an alternate connection for upload, which must then handle the commit itself.

If data must be uploaded *without* immediately committing as part of a longer chain of executions, you will need to construct the insertion SQL manually and then use `connector.execute()` with `commit=False` (or instantiate the Connector object with `autocommit=False`)

## Readouts<a id="readouts"></a>
You'll have noticed that kraken gives you a lot of readouts as it executes various functions. This can be very useful in some circumstances, but very annoying in others! For example, if you create a loop to execute a query 100 times with different variables, you probably don't want to kraken providing this degree of detail for every run.

The following functions `kraken.readout.suppress()` and `kraken.readout.activate()` functions can be used to amend this functionality globally across a script:

```python
# Normal
print("Normal behaviour:")
results = kraken.execute("RESEARCH", "SELECT TOP 10 * FROM patients")

# Readouts Switched Off
print("\nWith readouts turned off and manual printing instead:")
kraken.readout.suppress()

connector = kraken.create_connection("RESEARCH", autoclose=False, autocommit=False)
for x in range(1,11):
    print(f"Running with {x} row limit... ", end="")
    result = connector.execute(f"SELECT * FROM blood_tests WHERE patient_no = '{x}'")
    print("Downloaded!")

# Readouts Switched Back On
print("\nWith readouts turned back on:")
kraken.readout.activate()
results = kraken.execute("RESEARCH", "SELECT TOP 100 * FROM prescriptions")
```
Note that turning off readouts will also silence progress bars on SQL execution.

## Stats & Graphing<a id="stats_and_graphing"></a>
Kraken provides convenience functions for basic statistics and graphing. These functions can be used with `DataFrame` and `Result`, and `ResultList` objects if a `df_name` is provided. The `examine()` function can be used to get basic descriptive statistics such as nullity, cardinality, standard_deviation, skewness, kurtosis and outliers. The `graph()` function supports a number of plots such as density, bar, stacked, box, violin, and scatter. Inclusion of x and y variables, and x and y aggregation, will depend on the graph being used.

Note that these functions are intended to be useful for rapid exploration of datasets, and not a replacement for proper statistical analysis and graphing.

```python
# Example examination
# - unique ceiling defaults to 10, but can be increased to calculate category coverage for larger groups
# - when show_results=True (default), Jupyter notebooks will automatically display the results
# - returning to df_stats allows the StatsPack to be stored and called
df = kraken.execute(database="RESEARCH", sql="SELECT * FROM patients")
df_stats = kraken.examine(df, unique_ceiling=10, show_results=False, return_results=True)
display(df_stats.stats)
display(df_stats.categories)

```

Finally, graph a numeric column `DataFrame`, and explore the use of x/y aggregation. When it comes to aggregation, think about the nature of the graph and therefore use of continuous, ordinal, or categorial values. A few examples are below - feel free to experiment with your own datasets with `x_agg` and `y_agg`. Y-values will by default represent simple counts of the given column (note, not sum), but `y_agg` supports alternate bahviour.

```python
# Example graphing
# - saving to a variable (here: g, g1, etc), saves the aggregation used to produce the graph.

# density plot of year of birth:
g = kraken.graph(df=df, graph='density', x='year_of_birth', return_results=True)

# bar chart of date_of birth vs count, aggregated to 'year'
g1 = kraken.graph(df=df, graph='bar', x='date_of_birth', x_agg='year', return_results=True)

# bar chart of age group vs average result
kraken.graph(df=df, graph='bar', x='age', x_agg=10, y='result_numerical', y_agg='mean')

# bar chart of age group vs average result by gender
kraken.graph(df=df, graph='bar', x='age', x_agg=10, y='result_numerical', y_agg='mean', group_colour="gender")

# stacked bar chart of age and gender vs count, aggregated to groups of 10 years
kraken.graph(df=df, graph='stacked', x='age', x_agg=10, group_colour='sex')

# violin pliot of deprivation vs result by gender
kraken.graph(df=df_new, graph='violin', x='imd_decile', y='result_numerical', group_colour='gender')

# density graphs can plot on each axis
kraken.graph(df=df_new, graph='density', x='age', y='result_numerical', group_colour='gender')
```
