# read version from installed package
from importlib.metadata import version

__version__ = version("datakraken")

from kraken.analysis.data_manipulation import check_duplicates, examine
from kraken.classes.pack_lists import (
    QueryList,
    ResultList,
    convert_to_result_list,
)
from kraken.classes.packs import Query, Result
from kraken.connection.connector import create_connector
from kraken.credentials.credentials import Credentials
from kraken.credentials.helpers import (
    delete_credentials,
    fetch_credentials,
)
from kraken.credentials.save_connection import save_connection
from kraken.credentials.save_convenience import (
    save_connection_Cache,
    save_connection_DuckDB,
    save_connection_Informix,
    save_connection_Iris,
    save_connection_MariaDB,
    save_connection_MSSQL,
    save_connection_MySQL,
    save_connection_Oracle,
    save_connection_PostgreSQL,
)
from kraken.exporting.result_export import export_results
from kraken.graphing.graphing import graph
from kraken.importing.data_import import extract_spreadsheets
from kraken.parsing.parsing import Parser
from kraken.ribosome.ribosome import run
from kraken.ribosome.sql_execution import execute, execute_sql
from kraken.ribosome.sql_extraction import extract_sql
from kraken.support.progress import Progress
from kraken.support.readout import readout
from kraken.support.support import _load_filepaths as load_filepaths
from kraken.support.support import (
    calculate_runtime,
    datestamp,
    decode,
    encode,
    generate_where_clause,
    get_engine_path,
    set_default_alias,
    set_kraken_defaults,
)
from kraken.uploading.data_upload import upload, upload_results

__all__ = [
    "check_duplicates",
    "create_connector",
    "delete_credentials",
    "examine",
    "execute",
    "execute_sql",
    "export_results",
    "extract_sql",
    "fetch_credentials",
    "graph",
    "readout",
    "run",
    "save_connection_Cache",
    "save_connection_DuckDB",
    "save_connection_Informix",
    "save_connection_Iris",
    "save_connection_MariaDB",
    "save_connection_MSSQL",
    "save_connection_MySQL",
    "save_connection_Oracle",
    "save_connection_PostgreSQL",
    "upload",
    "upload_results",
    "QueryList",
    "ResultList",
    "convert_to_result_list",
    "Query",
    "Result",
    "extract_spreadsheets",
    "Credentials",
    "save_connection",
    "Parser",
    "Progress",
    "load_filepaths",
    "calculate_runtime",
    "datestamp",
    "decode",
    "encode",
    "generate_where_clause",
    "get_engine_path",
    "set_default_alias",
    "set_kraken_defaults",
]
