from io import BytesIO

import pandas as pd

from kraken.support.readout import readout


### File Preparation ###
# Prepare xlsx
def _prepare_results_xlsx(export_pack: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(
        path=buffer,
        engine="xlsxwriter",
        date_format="DD/MM/YYYY",
        datetime_format="DD/MM/YYYY HH:MM:SS",
    ) as writer:
        for df_name, dataframe in export_pack.items():
            readout.print(f"\n - writing sheet '{df_name}'...", end="")
            dataframe.to_excel(writer, sheet_name=df_name, index=False)
            readout.print(" complete", end="")
    return buffer.getvalue()


# Prepare csv
def _prepare_results_csv(
    export_pack: dict[str, pd.DataFrame], delimiter: str = ","
) -> bytes:
    buffer = BytesIO()
    for dataframe in export_pack.values():
        dataframe.to_csv(buffer, sep=delimiter, index=False)
    return buffer.getvalue()


# Prepare parquet
def _prepare_results_parquet(export_pack: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    for dataframe in export_pack.values():
        dataframe.to_parquet(buffer, index=False)
    return buffer.getvalue()
