# read version from installed package
from importlib.metadata import version

__version__ = version("datakraken")

from kraken.analysis.data_manipulation import check_duplicates, examine  # noqa: F401
from kraken.classes.pack_lists import (
    QueryList,  # noqa: F401
    ResultList,  # noqa: F401
    convert_to_result_list,  # noqa: F401
)
from kraken.classes.packs import Query, Result  # noqa: F401
from kraken.connection.connector import Connector, create_connector  # noqa: F401

# noqa: F401
from kraken.credentials.credentials import Credentials  # noqa: F401
from kraken.credentials.helpers import (  # noqa: F401
    delete_credentials,
    fetch_credentials,
)
from kraken.credentials.save_connection import save_connection  # noqa: F401
from kraken.credentials.save_convenience import (  # noqa: F401
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
from kraken.exporting.result_export import export_results  # noqa: F401
from kraken.graphing.graphing import graph  # noqa: F401
from kraken.importing.data_import import extract_spreadsheets  # noqa: F401
from kraken.parsing.parsing import Parser  # noqa: F401
from kraken.ribosome.ribosome import run  # noqa: F401
from kraken.ribosome.sql_execution import execute, execute_sql  # noqa: F401
from kraken.ribosome.sql_extraction import extract_sql  # noqa: F401
from kraken.support.progress import Progress  # noqa: F401
from kraken.support.readout import readout  # noqa: F401
from kraken.support.support import _load_filepaths as load_filepaths  # noqa: F401
from kraken.support.support import (  # noqa: F401
    calculate_runtime,
    datestamp,
    decode,
    encode,
    generate_where_clause,
    get_engine_path,
    set_default_alias,
    set_kraken_defaults,
)
from kraken.uploading.data_upload import upload, upload_results  # noqa: F401
