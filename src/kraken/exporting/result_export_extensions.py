from io import BytesIO

import pandas as pd

from kraken.support.readout import readout


### File Preparation ###
# Prepare xlsx
def _prepare_results_xlsx(
    export_pack: dict[str, pd.DataFrame], excel_tables: bool = True
) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(
        path=buffer,
        engine="xlsxwriter",
        date_format="DD/MM/YYYY",
        datetime_format="DD/MM/YYYY HH:MM:SS",
        engine_kwargs={
            "options": {"strings_to_formulas": False, "strings_to_urls": False}
        },
    ) as writer:
        for df_name, dataframe in export_pack.items():
            readout.print(f"\n - writing sheet '{df_name}'...", end="")
            headers = [str(column) for column in dataframe.columns]
            valid_headers = (
                all(
                    not (pd.api.types.is_scalar(column) and bool(pd.isna(column)))
                    for column in dataframe.columns
                )
                and len(headers) == len(set(header.casefold() for header in headers))
                and all(header.strip() for header in headers)
            )
            if excel_tables and valid_headers and headers and not dataframe.empty:
                dataframe.to_excel(
                    writer,
                    sheet_name=df_name,
                    startrow=1,
                    header=False,
                    index=False,
                )
                worksheet = writer.sheets[df_name]
                worksheet.add_table(
                    0,
                    0,
                    len(dataframe),
                    len(headers) - 1,
                    {"columns": [{"header": header} for header in headers]},
                )
            else:
                if excel_tables and not valid_headers:
                    readout.warn(
                        f"\n  -> WARNING: Sheet '{df_name}' has blank or duplicate "
                        "column names; exporting without an Excel table."
                    )
                dataframe.to_excel(writer, sheet_name=df_name, index=False)
            readout.print(" complete", end="")
    return buffer.getvalue()


# Prepare csv
def _prepare_results_csv(
    export_pack: dict[str, pd.DataFrame], delimiter: str = ","
) -> bytes:
    buffer = BytesIO()
    for dataframe in export_pack.values():
        csv_frame = dataframe.copy(deep=False)
        for position in range(len(dataframe.columns)):
            column = dataframe.iloc[:, position]
            if pd.api.types.is_datetime64_any_dtype(column.dtype) and not isinstance(
                column.dtype, pd.DatetimeTZDtype
            ):
                csv_frame.isetitem(
                    position,
                    column.map(
                        lambda value: "" if pd.isna(value) else value.isoformat(sep=" ")
                    ).array,
                )
        csv_frame.to_csv(buffer, sep=delimiter, index=False)
    return buffer.getvalue()


# Prepare parquet
def _prepare_results_parquet(export_pack: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    for dataframe in export_pack.values():
        dataframe.to_parquet(buffer, index=False)
    return buffer.getvalue()
