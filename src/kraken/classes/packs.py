from copy import copy, deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, overload

from IPython.display import display
from pandas import DataFrame

from kraken.classes.data_types import StatsPack
from kraken.graphing.graphing import graph as graph_main


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

    @overload
    def examine(
        self,
        unique_ceiling: int = ...,
        show_results: bool = ...,
        return_results: Literal[False] = False,
    ) -> None: ...

    @overload
    def examine(
        self,
        unique_ceiling: int = ...,
        show_results: bool = ...,
        return_results: Literal[True] = True,
    ) -> StatsPack: ...

    @overload
    def examine(
        self,
        unique_ceiling: int = ...,
        show_results: bool = ...,
        return_results: bool = ...,
    ) -> StatsPack | None: ...

    def examine(
        self,
        unique_ceiling: int = 10,
        show_results: bool = True,
        return_results: bool = False,
    ) -> StatsPack | None:
        """Performs high-level analysis of data in the Result's dataframe and outputs results.

        Args:
            unique_ceiling (int, optional): Ceiling below which a distinct number of values in a column will be included in 'category calculations'. Defaults to 10.
            show_results (bool, optional): Display results in python/notebook readouts. Defaults to True.
            return_results (bool, optional): Returns results as StatsPack. Defaults to False.

        Returns:
            StatsPack: Tuple including df name, stats dataframe, and category coverage dataframe.
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

        for temp_var_name, df in temp_dfs.items():
            locals()[temp_var_name] = df

        return eval(f'sqldf("""{query}""")')  # type: ignore[no-any-return]

    def graph(
        self,
        x: str,
        y: str | None = None,
        graph: (
            Literal[
                "aggregation",
                "density",
                "bar",
                "box",
                "violin",
                "scatter",
                "stacked",
            ]
            | None
        ) = None,
        x_agg: str | None = None,
        y_agg: str | None = None,
        group_colour: str | None = None,
        where_clause: str | None = None,
        convert_dates: bool = True,
        discard_null_aggs: bool = True,
        figsize: tuple[int, int] = (22, 7),
        bw_adjust: float = 0.5,
        alpha: bool | None = None,
        convert_categories_to_str: bool = False,
        linear_regression: bool = True,
        showfliers: bool = True,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        return_results: bool = False,
    ) -> DataFrame | None:
        """Graphing function for Result DataFrames, allowing selection of multiple graphs with different x, y, and aggregation arguments.

        Args:
            x (str): x-axis column.
            y (str, optional): y-axis column. If left empty, graphs requiring a y-axis value will plot an aggregation of the x-value here. Defaults to None.
            graph (str, optional): Selected graph. Processing (and acceptance) of input arguments varies by graph. Defaults to None.
            x_agg (int | str optional): Aggregation of the x-values into bins. Accepts 'year', 'month', etc for date columns, or integers for numeric columns. Defaults to None.
            y_agg (str, optional): Aggregation calculation to apply to y-values, for example 'sum', 'count', or 'mean'. Defaults to None.
            group_colour (str, optional): Column to group by, or apply, colouring. Defaults to None.
            where_clause (str, optional): SQL-style where clause to quickly filter DataFrame. Note that filters directly applied in the 'df=' are faster. Defaults to None.
            convert_dates (str, optional): Convert 'object' columns recognisable as dates. Defaults to True.
            discard_null_aggs (str, optional): Discard rows (and plots) with null y-values or aggregations. Defaults to True.
            figsize (tuple, optional): Graph size. Defaults to (22, 7).
            bw_adjust (float, optional): Granularity of density graphs. Lower values increase granularity. Defaults to 0.5.
            alpha (bool, optional): Transparency of fill. Defaults to None.
            convert_categories_to_str (bool, optional): If numeric categories (for example, year of birth) display
                with the x-axis forced to zero, set to True to convert numbers to categories. Note that this may change the ordering. Defaults to False.
            linear_regression (bool, optional): If plotting a scatter-graph, setting to False will hide the linear regression line. Defaults to True.
            showfliers (bool, optional): If plotting a boxplot, show outliers. Defaults to True.
            title (str, optional): Graph title. If None, generated from input data.
            x_label (str, optional): X-axis label. If None, generated from input data.
            y_label (str, optional): Y-axis label. If None, generated from input data.
            return_results (bool, optional): Returns resultant aggregation table created to plot graph as a DataFrame. Defaults to False.

        Returns:
            DataFrame: DataFrame of resultant aggregation table (if `return_results = True`).
        """
        return graph_main(
            self.df,
            x=x,
            y=y,
            graph=graph,
            x_agg=x_agg,
            y_agg=y_agg,
            group_colour=group_colour,
            where_clause=where_clause,
            convert_dates=convert_dates,
            discard_null_aggs=discard_null_aggs,
            figsize=figsize,
            bw_adjust=bw_adjust,
            alpha=alpha,
            convert_categories_to_str=convert_categories_to_str,
            linear_regression=linear_regression,
            showfliers=showfliers,
            title=title,
            x_label=x_label,
            y_label=y_label,
            return_results=return_results,
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
