from copy import copy, deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from IPython.display import display
from pandas import DataFrame
from pandasql import sqldf  # type: ignore[import-untyped]

from kraken.classes.data_types import StatsPack
from kraken.graphing.graphing import graph as graph_main
from kraken.graphing.models import GraphResult, GraphType


@dataclass
class SQLFile:
    filepath: Path
    filename: str
    db_alias: str | None
    platform: str
    raw_sql: str
    variables: dict[str, str]
    split_queries: bool = True
    arraysize: int | None = None
    parsing_report: str | None = None
    isolation_level: (
        Literal[
            "SERIALIZABLE",
            "REPEATABLE READ",
            "READ COMMITTED",
            "READ UNCOMMITTED",
            "AUTOCOMMIT",
        ]
        | None
    ) = None

    def copy(self, deep: bool = True) -> "SQLFile":
        """Copies the SQLFile.

        Args:
            deep (bool, optional): Performs a full (deep) copy of the SQLFile and all objects contained within. If False, performs a shallow copy of the top-level container only. Defaults to True (recommended).
        """
        if deep:
            return deepcopy(self)
        return copy(self)


class Query:
    def __init__(
        self,
        filename: str,
        df_name: str,
        sql: str,
        filepath: Path,
        *,
        db_alias: str | None = None,
        platform: str | None = None,
        arraysize: int | None = None,
        parsing_report: str | None = None,
        isolation_level: (
            Literal[
                "SERIALIZABLE",
                "REPEATABLE READ",
                "READ COMMITTED",
                "READ UNCOMMITTED",
                "AUTOCOMMIT",
            ]
            | None
        ) = None,
    ):
        self.filename: str = filename
        self.df_name: str = df_name
        self.sql: str = sql
        self.filepath: Path = filepath
        self.arraysize: int | None = arraysize
        self.db_alias: str | None = db_alias
        self.platform: str | None = platform
        self.parsing_report: str | None = parsing_report
        self.isolation_level: (
            Literal[
                "SERIALIZABLE",
                "REPEATABLE READ",
                "READ COMMITTED",
                "READ UNCOMMITTED",
                "AUTOCOMMIT",
            ]
            | None
        ) = isolation_level

    def __repr__(self) -> str:
        """
        Returns:
            str: A string representation of the Query object.
        """
        from kraken.support.support import _prepare_sql_snippet

        return (
            f"Query(filename='{self.filename}', db_alias='{self.db_alias}', "
            + f"df_name='{self.df_name}', sql='{_prepare_sql_snippet(self.sql, max_characters=50)}'"
            + f"{f', arraysize={self.arraysize}' if self.arraysize else ''})"
        )

    def copy(self) -> "Query":
        """Copies the Query."""
        return Query(
            filename=self.filename,
            df_name=self.df_name,
            sql=self.sql,
            filepath=self.filepath,
            db_alias=self.db_alias,
            platform=self.platform,
            parsing_report=self.parsing_report,
            isolation_level=self.isolation_level,
        )


class Result:
    df: DataFrame
    df_name: str
    filename: str | None = None
    filepath: Path | None = None
    db_alias: str | None = None
    platform: str | None = None
    sql: str | None = None
    query_pack: Query | None = None

    def __init__(
        self,
        df: DataFrame,
        df_name: str,
        filename: str | None = None,
        filepath: Path | None = None,
        db_alias: str | None = None,
        platform: str | None = None,
        sql: str | None = None,
        query_pack: Query | None = None,
    ):
        self.df: DataFrame = df
        self.df_name: str = df_name
        self.filename: str = filename
        self.filepath: Path = filepath
        self.db_alias: str = db_alias
        self.platform: str = platform
        self.sql: str = sql
        self.query_pack: Query = query_pack

    def __repr__(self) -> str:
        """
        Returns:
            str: A string representation of the Result object.
        """
        return f"Result(df_name='{self.df_name}' ({self.df.shape[1]} columns, {self.df.shape[0]} rows))"

    def copy(self, deep: bool = True) -> "Result":
        """Copies the Result.

        Args:
            deep (bool, optional): Performs a full (deep) copy of the Result and all objects contained within. If False, performs a shallow copy of the top-level container only. Defaults to True (recommended).
        """
        df_copy = self.df.copy(deep=deep)
        return Result(
            df=df_copy,
            df_name=self.df_name,
            filename=self.filename,
            filepath=self.filepath,
            db_alias=self.db_alias,
            platform=self.platform,
            sql=self.sql,
            query_pack=self.query_pack,
        )

    def examine(
        self,
        unique_ceiling: int = 10,
        show_results: bool = True,
        return_results: bool = False,
    ) -> StatsPack:
        """Performs high-level analysis of data in the Result's dataframe and outputs results.

        Args:
            unique_ceiling (int, optional): Ceiling below which a distinct number of values in a column will be included in 'category calculations'. Defaults to 10.
            show_results (bool, optional): Display results in python/notebook readouts. Defaults to True.
            return_results (bool, optional): Deprecated compatibility argument. A StatsPack is always returned.

        Returns:
            StatsPack: Result containing the dataframe name, column statistics, and category coverage dataframes.
        """
        from kraken.analysis.data_manipulation import examine

        return examine(
            df=self.df,
            df_name=self.df_name,
            unique_ceiling=unique_ceiling,
            show_results=show_results,
            return_results=return_results,
        )

    def query(self, query: str) -> DataFrame:
        """Allows SQL querying of the Result's dataframe.

        Args:
            query (str): SQL query, referencing the df as a table by its df_name.

        Returns:
            DataFrame: Query results as DataFrame.
        """
        temp_dfs = {self.df_name: self.df}
        result: DataFrame = sqldf(query, env=temp_dfs)
        return result

    def graph(
        self,
        x: str,
        y: str | None = None,
        graph: GraphType | str | None = None,
        x_agg: str | int | float | None = None,
        y_agg: str | None = None,
        group_colour: str | None = None,
        where_clause: str | None = None,
        convert_dates: bool = True,
        discard_null_aggs: bool = True,
        figsize: tuple[int, int] | None = None,
        bw_adjust: float = 0.5,
        alpha: float | None = None,
        convert_categories_to_str: bool = False,
        linear_regression: bool = False,
        showfliers: bool = True,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        return_results: bool = False,
        *,
        width: int | None = None,
        height: int | None = None,
        scroll: bool = False,
        show: bool = True,
        x_end: str | None = None,
        facet_row: str | None = None,
        facet_col: str | None = None,
        marginal_x: str | None = None,
        marginal_y: str | None = None,
        hover_columns: list[str] | None = None,
        error: str | None = None,
        confidence_level: float = 0.95,
    ) -> GraphResult:
        """Graphing function for Result DataFrames, allowing selection of multiple graphs with different x, y, and aggregation arguments.

        Args:
            x (str): x-axis column.
            y (str, optional): y-axis column. Box, violin, density, and scatter require real numeric or timedelta values. Aggregate graphs apply ``y_agg`` to x when omitted.
            graph (str, optional): Selected graph. Processing (and acceptance) of input arguments varies by graph. Defaults to None.
            x_agg (int | float | str, optional): Date period or finite positive numeric bin width. Numeric widths cannot bin timedeltas. Defaults to None.
            y_agg (str, optional): ``count``, ``countd``, ``sum``, ``mean``, ``mode``, or ``median``. Sum, mean, and median require quantitative values. Defaults to None.
            group_colour (str, optional): Column to group by, or apply, colouring. Defaults to None.
            where_clause (str, optional): SQL-style where clause to quickly filter DataFrame. Note that filters directly applied in the 'df=' are faster. Defaults to None.
            convert_dates (bool, optional): Convert recognised date axes. Required numeric axes and measures are converted automatically with a warning. Defaults to True.
            discard_null_aggs (bool, optional): Discard null aggregate rows and incomplete timeline ranges; otherwise incomplete timelines raise an error. Defaults to True.
            figsize (tuple, optional): Legacy fixed size in inches. Responsive by default.
            bw_adjust (float, optional): Granularity of density graphs. Lower values increase granularity. Defaults to 0.5.
            alpha (bool, optional): Transparency of fill. Defaults to None.
            convert_categories_to_str (bool, optional): If numeric categories (for example, year of birth) display
                with the x-axis forced to zero, set to True to convert numbers to categories. Note that this may change the ordering. Defaults to False.
            linear_regression (bool, optional): Add scatter regression lines. Defaults to False.
            showfliers (bool, optional): If plotting a boxplot, show outliers. Defaults to True.
            title (str, optional): Graph title. If None, generated from input data.
            x_label (str, optional): X-axis label. If None, generated from input data.
            y_label (str, optional): Y-axis label. If None, generated from input data.
            return_results (bool, optional): Deprecated compatibility argument. Prepared data is always returned. Defaults to False.
            width (int, optional): Explicit Plotly width in pixels, with a minimum of 10. Responsive by default.
            height (int, optional): Explicit Plotly height in pixels, with a minimum of 10.
            scroll (bool, optional): Use a wide canvas for horizontal scrolling.
            show (bool, optional): Display the interactive figure immediately. Defaults to True.
            x_end (str, optional): End-date column required for timeline graphs.
            facet_row (str, optional): Column used to create facet rows where supported.
            facet_col (str, optional): Column used to create facet columns where supported.
            marginal_x (str, optional): Scatter marginal renderer for x.
            marginal_y (str, optional): Scatter marginal renderer for y.
            hover_columns (list[str], optional): Additional hover columns where supported.
            error (str, optional): ``confidence_interval`` for supported mean aggregations.
            confidence_level (float, optional): Confidence level strictly between zero and one.

        Returns:
            GraphResult: Interactive figure and prepared graph data.

        Raises:
            GraphingError: If graph capabilities, columns, dtypes, conversion,
                aggregation, input data, or rendering are invalid.
        """
        return graph_main(
            self.df,
            x=x,
            x_end=x_end,
            y=y,
            facet_row=facet_row,
            facet_col=facet_col,
            marginal_x=marginal_x,
            marginal_y=marginal_y,
            hover_columns=hover_columns,
            error=error,
            confidence_level=confidence_level,
            graph=graph,
            x_agg=x_agg,
            y_agg=y_agg,
            group_colour=group_colour,
            where_clause=where_clause,
            convert_dates=convert_dates,
            discard_null_aggs=discard_null_aggs,
            figsize=figsize,
            width=width,
            height=height,
            scroll=scroll,
            bw_adjust=bw_adjust,
            alpha=alpha,
            convert_categories_to_str=convert_categories_to_str,
            linear_regression=linear_regression,
            showfliers=showfliers,
            title=title,
            x_label=x_label,
            y_label=y_label,
            return_results=return_results,
            show=show,
        )

    def check_duplicates(self, columns: str | list[str] | None = None) -> DataFrame:
        """Check whether data is unique in a column or over a set of columns.
        Can be used to determine applicability as a unique identifier or primary key.
        Returns duplicates over the given column set, if found.

        Args:
            columns (str | list[str], optional): Column or column set to check for duplicates. Defaults to None, checking the first column.

        Raises:
            ValueError: If a given column does not exist in the DataFrame.

        Returns:
            DataFrame: DataFrame of duplicates, if found
        """
        from kraken.analysis.data_manipulation import check_duplicates

        return check_duplicates(df=self.df, columns=columns)

    def info(self) -> None:
        message = f"{self.df_name}"
        print(message)
        print("-" * len(message))
        print("type:      Result")
        print(f"df_name:   {self.df_name}")
        print(f"filepath:  {self.filepath}")
        print(f"db_alias:  {self.db_alias}")
        print(f"platform:  {self.platform}")
        print(f"\nsql:\n{self.sql}")
        print("df:")
        display(self.df)
