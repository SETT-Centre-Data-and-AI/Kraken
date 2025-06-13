import oracledb

from kraken.support.support import decode

oracle_client_dir = decode("ORACLE_CLIENT", "KRAKEN_DEFAULT")
oracle_db_initialised = False

try:
    # Try to initialize with set default
    oracledb.init_oracle_client(lib_dir=oracle_client_dir)
    oracle_db_initialised = True
except oracledb.ProgrammingError:
    # Catch already initialized error
    oracle_db_initialised = True
except oracledb.DatabaseError:
    # Try to initialize with oracledb search for drivers
    try:
        oracledb.init_oracle_client()
        oracle_db_initialised = True
    except oracledb.DatabaseError:
        # On failure, ignore and revert to thin mode
        pass
