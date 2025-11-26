from kraken.credentials.save_connection import save_connection


### MSSQL ###
def save_connection_MSSQL(
    alias: str,
    server: str,
    database: str,
    username: str | None = None,
    password: str | None = None,
    default: bool = False,
    sqldriver: str = "pyodbc",
    driver_version: int = 17,
    trust_server_certificate: bool = False,
    autosave: bool = False,
) -> None:
    """
    Save a SQL Server database connection string under a callable alias and username.
    If 'username' = '', then the connection will be saved to use Windows Authentication, and any password is ignored.
    If 'default' is set to True, this username (or Windows Authenticated login method) will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                    Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        server (str):                   Server
        database (str):                 Database name
        username (str, optional):       Username. If None, password is ignored and Windows Authentication is used. Defaults to None.
        password (str, optional):       Password. Ignored if username = None. Defaults to None.
        driver_version (int, optional): ODBC driver version. Defaults to 17.
        default (bool, optional):       If True, saves username as default for database alias. Defaults to False.
        sqldriver (str, optional):      SQL Driver to use for connections. Defaults to "pyodbc".
        autosave (bool, optional):      If True, saves regardless of connection success. Defaults to False.
    """
    platform = "mssql"
    login = f"{username}:{password}@" if username and password else ""
    trusted_connection = "" if username and password else "&trusted_connection=yes"
    trusted_server_certificate = (
        "&TrustServerCertificate=yes" if trust_server_certificate else ""
    )
    connection_string = (
        f"mssql+{sqldriver}://"
        f"{login}"
        f"{server}/{database}"
        f"?driver=ODBC+Driver+{driver_version}+for+SQL+Server"
        f"{trusted_server_certificate}"
        f"{trusted_connection}"
    )

    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### Oracle ###
def save_connection_Oracle(
    alias: str,
    username: str,
    password: str,
    host: str,
    service: str,
    port: str | int = 1521,
    default: bool = False,
    sqldriver: str = "oracledb",
    autosave: bool = False,
) -> None:
    """
    Save an Oracle database connection string under a callable alias and username.
    If 'default' is set to True, this username will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                    Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        username (str):                 Username
        password (str):                 Password
        host (str):                     Database host server
        service (str):                  Database service address
        port (str | int, optional):     Port. Defaults to 1521.
        default (bool, optional):       If True, saves username as default for database alias. Defaults to False.
        sqldriver (str, optional):      SQL Driver to use for connections. Defaults to "oracledb".
        autosave (bool, optional):      If True, saves regardless of connection success. Defaults to False.
    """
    platform = "oracle"
    connection_string = (
        f"oracle+{sqldriver}://" + f"{username}:{password}"
    ) + f"@{host}:{str(port)}/?service_name={service}"

    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### Informix ###
def save_connection_Informix(
    alias: str,
    username: str,
    password: str,
    database: str,
    host: str,
    server: bool,
    default: bool = False,
    autosave: bool = False,
) -> None:
    """
    Save an Informix database connection string under a callable alias and username.
    If 'default' is set to True, this username will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        username (str):             Username
        password (str):             Password
        database (str):             Database name
        host (str):                 Database host
        server (str):               Database server
        default (bool, optional):   If True, saves username as default for database alias. Defaults to False.
        autosave (bool, optional):  If True, saves regardless of connection success. Defaults to False.
    """
    platform = "informix"
    driver = "{IBM INFORMIX ODBC DRIVER (64-Bit)}"
    protocol = "onsoctcp"

    connection_string = (
        f"DRIVER={driver};\n"
        f"Host={host};\n"
        f"Server={server};\n"
        f"Protocol={protocol};\n"
        f"Database={database};\n"
        f"Uid={username};\n"
        f"Pwd={password}\n"
    )

    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### Intersystems Cache ###
def save_connection_Cache(
    alias: str,
    username: str,
    password: str,
    database: str,
    server: bool,
    default: bool = False,
    autosave: bool = False,
    driver: str = "{InterSystems ODBC}",
) -> None:
    """
    Save an Intersystems Cache database connection string under a callable alias and username.
    If 'default' is set to True, this username will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        username (str):             Username
        password (str):             Password
        datbase (str):              Database/namespace
        server (str):               Database server
        default (bool, optional):   If True, saves username as default for database alias. Defaults to False.
        autosave (bool, optional):  If True, saves regardless of connection success. Defaults to False.
    """

    platform = "cache"
    connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};"
    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### Intersystems Cache ###
def save_connection_Iris(
    alias: str,
    username: str,
    password: str,
    database: str,
    server: bool,
    default: bool = False,
    autosave: bool = False,
    driver: str = "{InterSystems Iris ODBC35}",
) -> None:
    """
    Save an Intersystems Iris database connection string under a callable alias and username.
    If 'default' is set to True, this username will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        username (str):             Username
        password (str):             Password
        datbase (str):              Database/namespace
        server (str):               Database server
        default (bool, optional):   If True, saves username as default for database alias. Defaults to False.
        autosave (bool, optional):  If True, saves regardless of connection success. Defaults to False.
    """

    platform = "iris"
    connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};"
    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### MariaDB ###
def save_connection_MariaDB(
    alias: str,
    host: str,
    database: str,
    username: str,
    password: str,
    port: str | int = 3306,
    default: bool = False,
    autosave: bool = False,
) -> None:
    """
    Save a MariaDB database connection string under a callable alias and username.
    If 'default' is set to True, this username will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                    Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        host (str):                     Database host server
        database (str):                 Database name
        username (str):                 Username
        password (str):                 Password
        port (str | int, optional):     Port. Defaults to 3306.
        default (bool, optional):       If True, saves username as default for database alias. Defaults to False.
    """

    platform = "mariadb"
    connection_string = (
        f"mariadb+pymysql://{username}:{password}@{host}:{port}/{database}"
    )

    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### PostgreSQL ###
def save_connection_PostgreSQL(
    alias: str,
    host: str,
    database: str,
    username: str,
    password: str,
    port: str | int = 5432,
    default: bool = False,
    autosave: bool = False,
) -> None:
    """
    Save a PostgreSQL database connection string under a callable alias and username.
    If 'default' is set to True, this username will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        host (str):                 Database host server
        database (str):             Database name
        username (str):             Username
        password (str):             Password
        port (str | int, optional): Port. Defaults to 5432.
        default (bool, optional):   If True, saves username as default for database alias. Defaults to False.
    """

    platform = "postgresql"
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"

    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### MySQL ###
def save_connection_MySQL(
    alias: str,
    host: str,
    database: str,
    username: str,
    password: str,
    port: str | int = 3306,
    default: bool = False,
    autosave: bool = False,
) -> None:
    """
    Save a MySQL database connection string under a callable alias and username.
    If 'default' is set to True, this username will be used as the default for the given alias. Saves as:

        {username}@{alias} -> {connection_string}

    Args:
        alias (str):                    Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        host (str):                     Database host server
        database (str):                 Database name
        username (str):                 Username
        password (str):                 Password
        port (str | int, optional):     Port. Defaults to 3306.
        default (bool, optional):       If True, saves username as default for database alias. Defaults to False.
    """

    platform = "mariadb"
    connection_string = (
        f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
    )

    save_connection(
        alias=alias,
        connection_string=connection_string,
        username=username,
        password=password,
        platform=platform,
        default=default,
        autosave=autosave,
    )


### DuckDB ###
def save_connection_DuckDB(
    alias: str,
    database: str | None = None,
    autosave: bool = False,
) -> None:
    """
    Save a DuckDB database connection string under a callable alias and username.
    As usernames are not supported with DuckDB, credentials are always saved under the alias as a default.
    Leave database blank to instantiate an in-memory DuckDB database, or provide an absolute or relative path
    to the database. If not appended with .duckdb or .db, .duckdb will be automatically appended.

    Args:
        alias (str):                Alias for the database. Connection engines can be created using this alias, and can be fed into kraken from SQL files.
        database (str | None):      Leave blank for an in-memory DuckDB database, or provide a path to a duckdb database
        username (str):             Username
        password (str):             Password
        default (bool, optional):   If True, saves username as default for database alias. Defaults to False.
    """

    platform = "duckdb"
    if database is None:
        database = ":memory:"
    else:
        database = (
            f"{database}.duckdb"
            if not database.endswith(".duckdb") and not database.endswith(".db")
            else database
        )

    connection_string = f"duckdb:///{database}"

    save_connection(
        alias=alias,
        connection_string=connection_string,
        platform=platform,
        default=True,
        autosave=autosave,
    )
