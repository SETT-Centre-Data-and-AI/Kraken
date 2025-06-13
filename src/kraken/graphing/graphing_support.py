from pandas import DataFrame, Series
from pandasql import sqldf  # type: ignore[import-untyped]


def _initialise_graph_dataframe(
    df: DataFrame, where_clause: str | None = None
) -> DataFrame:
    """Initialises Result's dataframe with where_clause if applicable

    Args:
        df (Result | Result): DataFrame or Result containing DataFrame
        where_clause (str, optional): SQL-style where clause to apply to DataFrame. Defaults to None.

    Raises:
        ValueError: df must be a DataFrame or object containing a df

    Returns:
        _type_: DataFrame
    """
    if not isinstance(df, DataFrame):
        try:
            df = df.df
        except AttributeError as e:
            raise e

    input_dtype_dict = df.dtypes.to_dict()
    if not where_clause:
        df = df.copy()
    else:
        words = where_clause.split()
        if len(words) > 0 and words[0].lower() == "where":
            words = words[1:]
        where_clause = " ".join(words)
        df = (
            sqldf(f"SELECT * FROM df WHERE {where_clause}", env=locals())
            .copy()
            .astype(input_dtype_dict)
        )

    if len(df) == 0:
        raise ValueError("No rows in DataFrame")

    return df


def aggregate_y(y_agg: str, values: DataFrame | Series) -> int | float | Series | None:
    """Applies y-aggragate calculation

    Args:
        y_agg (str): Aggregation calculation
        values: Column values

    Returns:
        Column values
    """
    result: int | float | Series | None
    y_agg = "count" if not y_agg else y_agg
    if y_agg == "count":
        result = values.count()
    elif y_agg == "countd":
        result = values.nunique()
    elif y_agg == "sum":
        result = values.sum()
    elif y_agg == "mean":
        result = values.mean()
    elif y_agg == "mode":
        result = values.mode().iloc[0] if not values.mode().empty else None
    elif y_agg == "median":
        result = values.median()
    else:
        raise ValueError(f"Aggregate '{y_agg}' not recognised")
    return result


def pretty_label(name: str) -> str:
    return name.replace("_", " ").lower().title()
