from __future__ import annotations

import inspect
from collections import UserList
from collections.abc import Iterable
from typing import Literal, overload

from pandas import DataFrame
from pandasql import sqldf  # type: ignore[import-untyped]

from kraken.classes.data_types import StatsPack
from kraken.classes.packs import Query, Result
from kraken.exceptions import GraphColumnError
from kraken.graphing.graphing import graph as graph_main
from kraken.graphing.models import GraphResult, GraphType
from kraken.support.readout import readout


class ResultList(UserList[Result]):
    def __init__(self, initial_data: list[Result] | None = None):
        super().__init__(initial_data)

    def __remove(self, item: Result) -> None:
        self.data.remove(item)

    @overload
    def __getitem__(self, index: int) -> Result: ...

    @overload
    def __getitem__(self, index: slice) -> ResultList: ...

    @overload
    def __getitem__(self, index: str) -> Result: ...

    def __getitem__(self, index: int | slice | str) -> Result | ResultList:
        if isinstance(index, str):
            return self.get(index)
        return super().__getitem__(index)

    def copy(self, deep: bool = True) -> ResultList:
        """Copies the ResultList.

        Args:
            deep (bool, optional): Performs a full (deep) copy of the ResultList and all objects
            contained within. If False, performs a shallow copy of the top-level container only.
            Defaults to True (recommended).
        """
        copy = ResultList([result.copy(deep=deep) for result in self.data])
        return copy

    def append(self, item: Result) -> None:
        """Append a Result to the end of this list.

        Args:
            item (Result): Result object to append.

        Raises:
            TypeError: If item is not a Result.
        """
        if not isinstance(item, Result):
            raise TypeError("Only Result objects can be appended")
        super().append(item)

    def extend(self, items: Iterable[Result]) -> None:
        """Append each Result in an iterable to the end of this list.

        Args:
            items (Iterable[Result]): Iterable of Result objects to append.

        Raises:
            TypeError: If any item in the iterable is not a Result.
        """
        for item in items:
            if not isinstance(item, Result):
                raise TypeError("Only Result objects can be extended")
        super().extend(items)

    @overload
    def get(
        self, search_value: str, field_name: str = ..., get_all: Literal[False] = False
    ) -> Result: ...

    @overload
    def get(
        self, search_value: str, field_name: str = ..., get_all: bool = ...
    ) -> Result | ResultList: ...

    def get(
        self, search_value: str, field_name: str = "df_name", get_all: bool = False
    ) -> Result | ResultList:
        """Find Result objects whose selected field matches a value.

        When ``get_all`` is False, returns the first match and warns if there
        are duplicates. When True, returns all matches in a ResultList.

        Args:
            search_value (str): Value to match against the selected field.
            field_name (str, optional): Result field to search. Defaults to "df_name".
            get_all (bool, optional): Whether to return every match. Defaults to False.

        Raises:
            KeyError: If field_name is not a field declared on Result.
            ValueError: If no Result matches search_value.

        Returns:
            Result | ResultList: The first matching Result, or all matches when get_all is True.
        """
        if field_name not in list(Result.__annotations__):
            raise KeyError(f"Cannot search '{field_name}' - no such attribute")
        found_results = ResultList()

        for result in self.data:
            field_value = getattr(result, field_name, None)
            if field_value == search_value:
                if isinstance(found_results, ResultList):
                    found_results.append(result)
                else:
                    return result

        if not len(found_results):
            raise ValueError(f"No {field_name} found called '{search_value}'")

        if not get_all:
            if len(found_results) > 1:
                readout.warn(
                    f"\nWARNING: {len(found_results)} duplicate matches found, only returning first match \n -> ",
                    end="",
                )
            return found_results[0]
        else:
            readout.print(f"Returned {len(found_results)} results for {search_value}")
            return found_results

    def drop(
        self,
        search_value: str | Result,
        field_name: str = "df_name",
        drop_all: bool = True,
    ) -> None:
        """Remove a Result object or matching Result objects from this list.

        Passing a Result removes that object. Passing a string searches the
        selected field; duplicate matches are warned about and either all or
        only the first are removed according to ``drop_all``.

        Args:
            search_value (str | Result): Result object to remove, or value to search for.
            field_name (str, optional): Result field to search for a string value. Defaults to "df_name".
            drop_all (bool, optional): Whether to remove every match. Defaults to True.

        Raises:
            KeyError: If field_name is not a field declared on Result.
            ValueError: If no matching Result is found, or the supplied Result is not in this list.
        """
        if isinstance(search_value, Result):
            self.__remove(search_value)
            return
        if field_name not in Result.__annotations__:
            raise KeyError(f"Cannot search '{field_name}' - no such attribute")
        results = [
            result
            for result in self.data
            if getattr(result, field_name, None) == search_value
        ]
        if not results:
            raise ValueError(f"No {field_name} found called '{search_value}'")
        if len(results) > 1:
            removal_scope = (
                f"all {len(results)} matches" if drop_all else "only the first match"
            )
            readout.warn(
                f"\nWARNING: {len(results)} duplicate matches found; {removal_scope} will be dropped \n -> ",
                end="",
            )
        if not drop_all:
            results = results[:1]
        for result in results:
            self.__remove(result)

    def remove(
        self,
        search_value: str | Result,
        field_name: str = "df_name",
        drop_all: bool = True,
    ) -> None:
        """Remove a Result or matching Result objects; equivalent to ``drop``.

        A Result argument removes that object. A string argument is matched
        against ``field_name``; duplicate matches are warned about and
        ``drop_all`` determines whether all or only the first match is removed.

        Args:
            search_value (str | Result): Result object to remove, or value to search for.
            field_name (str, optional): Result field to search for a string value. Defaults to "df_name".
            drop_all (bool, optional): Whether to remove every match. Defaults to True.
        """
        self.drop(search_value=search_value, field_name=field_name, drop_all=drop_all)

    def convert_to_dict(self) -> dict[str, DataFrame]:
        """Return the list's DataFrames keyed by their names.

        If multiple Results have the same ``df_name``, later entries receive
        a numbered suffix that avoids collisions with existing names.

        Returns:
            dict[str, DataFrame]: Mapping from unique DataFrame names to DataFrames.
        """
        original_names = [item_pack.df_name for item_pack in self]
        item_dict: dict[str, DataFrame] = {}

        for item_pack in self:
            if item_pack.df_name not in item_dict:
                item_dict[item_pack.df_name] = item_pack.df
            else:
                for n in range(len(original_names)):
                    new_df_name = f"{item_pack.df_name}_{n + 2:02d}"
                    if (
                        new_df_name not in item_dict
                        and new_df_name not in original_names
                    ):
                        item_dict[new_df_name] = item_pack.df
                        break

        return item_dict

    def query(self, query: str) -> DataFrame:
        """Allows SQL querying of the ResultList's DataFrames.

        Args:
            query (str): SQL query, referencing any dfs as tables by the associated Result's df_name.

        Returns:
            DataFrame: Query results as DataFrame.
        """
        temp_dfs = self.convert_to_dict()
        result: DataFrame = sqldf(query, env=temp_dfs)
        return result

    def examine(
        self,
        df_name: str,
        unique_ceiling: int = 10,
        show_results: bool = True,
        return_results: bool = False,
    ) -> StatsPack:
        """Performs high-level analysis of data in a Result's dataframe and outputs results.

        Args:
            df_name (str, optional): Select a Result to examine by df_name.
            unique_ceiling (int, optional): Ceiling below which a distinct number of values in a column will be included in 'category calculations'. Defaults to 10.
            show_results (bool, optional): Display results in python/notebook readouts. Defaults to True.
            return_results (bool, optional): Deprecated compatibility argument. A StatsPack is always returned.

        Returns:
            StatsPack: Result containing the dataframe name, column statistics, and category coverage dataframes.
        """
        if df_name is None:
            raise ValueError(
                "When using .examine() on a ResultList, you must choose a Result by passing df_name=''"
            )

        result = self.get(df_name)

        return result.examine(
            unique_ceiling=unique_ceiling,
            show_results=show_results,
            return_results=return_results,
        )

    def graph(
        self,
        df_name: str,
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
        """Graphing function for Result DataFrames in a ResultList, allowing selection of multiple graphs with different x, y, and aggregation arguments.

        Args:
            df_name (str): Result df_name for graphing.
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
        if df_name is None:
            raise GraphColumnError(
                "ResultList graph received df_name=None. Select a Result by passing "
                "the df_name of an existing Result."
            )

        result = self.get(df_name)

        return graph_main(
            result.df,
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

    def check_duplicates(
        self, df_name: str, columns: str | list[str] | None = None
    ) -> DataFrame:
        """Check whether data is unique in a column or over a set of columns.
        Can be used to determine applicability as a unique identifier or primary key.
        Returns duplicates over the given column set, if found.

        Args:
            df_name (str): Input DataFrame to check.
            columns (str | list[str], optional): Column or column set to check for duplicates. Defaults to None, checking the first column.

        Raises:
            ValueError: If a given column does not exist in the DataFrame.

        Returns:
            DataFrame: DataFrame of duplicates, if found
        """
        result = self.get(df_name)
        return result.check_duplicates(columns=columns)


class QueryList(UserList[Query]):
    def __init__(self, initial_data: list[Query] | None = None):
        super().__init__(initial_data)

    def __remove(self, item: Query) -> None:
        self.data.remove(item)

    @overload
    def __getitem__(self, index: int) -> Query: ...

    @overload
    def __getitem__(self, index: slice) -> QueryList: ...

    @overload
    def __getitem__(self, index: str) -> Query: ...

    def __getitem__(self, index: int | slice | str) -> Query | QueryList:
        if isinstance(index, str):
            return self.get(index)
        return super().__getitem__(index)

    def append(self, item: Query) -> None:
        """Append a Query to the end of this list.

        Args:
            item (Query): Query object to append.

        Raises:
            TypeError: If item is not a Query.
        """
        if not isinstance(item, Query):
            raise TypeError("Only Query objects can be appended")
        super().append(item)

    def extend(self, items: Iterable[Query]) -> None:
        """Append each Query in an iterable to the end of this list.

        Args:
            items (Iterable[Query]): Iterable of Query objects to append.

        Raises:
            TypeError: If any item in the iterable is not a Query.
        """
        for item in items:
            if not isinstance(item, Query):
                raise TypeError("Only Query objects can be extended")
        super().extend(items)

    @overload
    def get(
        self, search_value: str, field_name: str = ..., get_all: Literal[False] = False
    ) -> Query: ...

    @overload
    def get(
        self, search_value: str, field_name: str = ..., get_all: bool = ...
    ) -> Query | QueryList: ...

    def get(
        self, search_value: str, field_name: str = "df_name", get_all: bool = False
    ) -> Query | QueryList:
        """Find Query objects whose selected field matches a value.

        When ``get_all`` is False, returns the first match and warns if there
        are duplicates. When True, returns all matches in a QueryList.

        Args:
            search_value (str): Value to match against the selected field.
            field_name (str, optional): Query field to search. Defaults to "df_name".
            get_all (bool, optional): Whether to return every match. Defaults to False.

        Raises:
            KeyError: If field_name is not an argument of Query.__init__.
            ValueError: If no Query matches search_value.

        Returns:
            Query | QueryList: The first matching Query, or all matches when get_all is True.
        """
        sig = inspect.signature(Query.__init__)
        args = [name for name in sig.parameters if name != "self"]
        if field_name not in args:
            raise KeyError(f"Cannot search '{field_name}' - no such attribute")
        found_results = QueryList()
        for result in self.data:
            field_value = getattr(result, field_name, None)
            if field_value == search_value:
                if isinstance(found_results, QueryList):
                    found_results.append(result)
                else:
                    return result

        if not len(found_results):
            raise ValueError(f"No {field_name} found called '{search_value}'")

        if not get_all:
            if len(found_results) > 1:
                readout.warn(
                    f"\nWARNING: {len(found_results)} duplicate matches found, only returning first match \n -> ",
                    end="",
                )
            return found_results[0]
        else:
            readout.print(f"Returned {len(found_results)} results for {search_value}")
            return found_results

    def drop(
        self,
        search_value: str | Query,
        field_name: str = "df_name",
        drop_all: bool = True,
    ) -> None:
        """Remove a Query object or matching Query objects from this list.

        Passing a Query removes that object. Passing a string searches the
        selected field; duplicate matches are warned about and either all or
        only the first are removed according to ``drop_all``.

        Args:
            search_value (str | Query): Query object to remove, or value to search for.
            field_name (str, optional): Query field to search for a string value. Defaults to "df_name".
            drop_all (bool, optional): Whether to remove every match. Defaults to True.

        Raises:
            KeyError: If field_name is not an argument of Query.__init__.
            ValueError: If no matching Query is found, or the supplied Query is not in this list.
        """
        if isinstance(search_value, Query):
            self.__remove(search_value)
            return
        sig = inspect.signature(Query.__init__)
        args = [name for name in sig.parameters if name != "self"]
        if field_name not in args:
            raise KeyError(f"Cannot search '{field_name}' - no such attribute")
        items = [
            item
            for item in self.data
            if getattr(item, field_name, None) == search_value
        ]
        if not items:
            raise ValueError(f"No {field_name} found called '{search_value}'")
        if len(items) > 1:
            removal_scope = (
                f"all {len(items)} matches" if drop_all else "only the first match"
            )
            readout.warn(
                f"\nWARNING: {len(items)} duplicate matches found; {removal_scope} will be dropped \n -> ",
                end="",
            )
        if not drop_all:
            items = items[:1]
        for item in items:
            self.__remove(item)

    def remove(
        self,
        search_value: str | Query,
        field_name: str = "df_name",
        drop_all: bool = True,
    ) -> None:
        """Remove a Query or matching Query objects; equivalent to ``drop``.

        A Query argument removes that object. A string argument is matched
        against ``field_name``; duplicate matches are warned about and
        ``drop_all`` determines whether all or only the first match is removed.

        Args:
            search_value (str | Query): Query object to remove, or value to search for.
            field_name (str, optional): Query field to search for a string value. Defaults to "df_name".
            drop_all (bool, optional): Whether to remove every match. Defaults to True.
        """
        self.drop(search_value=search_value, field_name=field_name, drop_all=drop_all)

    def copy(self) -> QueryList:
        """Copies the QueryList."""
        copy = QueryList([query.copy() for query in self.data])
        return copy

    def convert_to_dict(self) -> dict[str, str]:
        """Return the queries' SQL strings keyed by their DataFrame names.

        If multiple Queries have the same ``df_name``, later entries receive
        a numbered suffix that avoids collisions with existing names.

        Returns:
            dict[str, str]: Mapping from unique DataFrame names to SQL strings.
        """
        original_names = [item_pack.df_name for item_pack in self]
        item_dict = {}

        for item_pack in self:
            if item_pack.df_name not in item_dict:
                item_dict[item_pack.df_name] = item_pack.sql
            else:
                for n in range(len(original_names)):
                    new_df_name = f"{item_pack.df_name}_{n + 2:02d}"
                    if (
                        new_df_name not in item_dict
                        and new_df_name not in original_names
                    ):
                        item_dict[new_df_name] = item_pack.sql
                        break

        return item_dict


def convert_to_result_list(results: dict[str, DataFrame]) -> ResultList:
    """Creates a ResultList object from a dictionary of DataFrames.

    Args:
        results (dict[str, DataFrame]): Dictionary of DataFrames.

    Raises:
        TypeError: if results is not a dictionary as {str: DataFrame}.

    Returns:
        ResultList: Results as a ResultList object.
    """
    error_message = "Variable 'results' should be a dictionary of DataFrames as {str: DataFrame, ...}."

    if not isinstance(results, dict):
        raise TypeError(error_message)

    result_list = ResultList()
    for df_name, df in results.items():
        if not isinstance(df_name, str) or not isinstance(df, DataFrame):
            raise TypeError(error_message)
        else:
            result_list.append(Result(df=df, df_name=df_name))

    return result_list
