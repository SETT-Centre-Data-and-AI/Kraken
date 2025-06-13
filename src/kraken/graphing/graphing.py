from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.dates import DateFormatter

from kraken.graphing.graphing_graphs import (
    graph_bar,
    graph_box,
    graph_density,
    graph_scatter,
    graph_stacked,
    graph_violin,
)
from kraken.graphing.graphing_support import (
    _initialise_graph_dataframe,
    aggregate_y,
    pretty_label,
)
from kraken.graphing.graphing_support_lists import (
    dtype_list_is_numeric,
    graph_list,
    x_aggs_supported_date,
    y_aggs_supported,
)
from kraken.support.readout import readout


def graph(
    df: pd.DataFrame,
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
    figsize: tuple = (22, 7),
    bw_adjust: float = 0.5,
    alpha: float | None = None,
    convert_categories_to_str: bool = False,
    linear_regression: bool = True,
    showfliers: bool = True,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    return_results: bool = False,
) -> pd.DataFrame | None:
    """Graphing function for DataFrames, allowing selection of multiple graphs with different x, y, and aggregation arguments.

    Args:
        df (pd.DataFrame): Input DataFrame.
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
        alpha (float, optional): Transparency of fill. Defaults to None.
        convert_categories_to_str (bool, optional): If numeric categories (for example, year of birth) display displeasingly with the x-axis forced to zero, set to True to convert numbers to categories. Note that this may change the ordering. Defaults to False.
        linear_regression (bool, optional): If plotting a scatter-graph, setting to False will hide the linear regression line. Defaults to True.
        showfliers (bool, optional): If plotting a boxplot, show outliers. Defaults to True.
        title (str, optional): Graph title. If None, generated from input data.
        x_label (str, optional): X-axis label. If None, generated from input data.
        y_label (str, optional): Y-axis label. If None, generated from input data.
        return_results (bool, optional): Returns resultant aggregation table created to plot graph as a DataFrame. Defaults to False.

    Returns:
        DataFrame: DataFrame of resultant aggregation table (if `return_results = True`).
    """
    from kraken.analysis.data_manipulation import date_converter_df

    # Initialise DataFrame
    df = _initialise_graph_dataframe(df, where_clause=where_clause)

    # Prepare Input Columns
    input_df_columns = [col for col in df.columns]
    group_columns = [col for col in [group_colour] if col]
    optional_columns = [col for col in [y] + group_columns if col is not None]
    all_columns = list(set([x] + optional_columns))
    optional_columns = (
        optional_columns.remove(x) if x in optional_columns else optional_columns  # type: ignore[func-returns-value]
    )

    # Lower Variable Case
    graph = graph.lower() if graph else graph  # type: ignore[assignment]
    x_agg = x_agg.lower() if x_agg and isinstance(x_agg, str) else x_agg
    y_agg = y_agg.lower() if y_agg else y_agg

    # Check Columns
    for col in all_columns:
        if col not in input_df_columns:
            raise ValueError(f"Column '{col}' not found in DataFrame")

    # Check Graph Settings
    graph_mode = True if graph else False
    if not graph_mode:
        graph = "aggregation"
    graph_settings = graph_list[graph]  # type: ignore[index]

    if not graph_mode:
        readout.warn(
            f"Note: no graph selected - aggregating data only. Supported graphs: {[x for x in graph_list]}"
        )
    else:
        if not graph_settings:
            raise ValueError(
                f"Graph '{graph}' not supported. Supported graphs: {[g for g in graph_list]}"
            )

    # Prepare DataFrame
    df = df[all_columns]
    df = date_converter_df(df, all_columns, readouts=True) if convert_dates else df

    column_is_numeric_dict = {
        col: dtype_list_is_numeric.get(str(df[col].dtype)) for col in df.columns
    }

    for col, v in column_is_numeric_dict.items():
        if v is None:
            raise ValueError(
                f"Column '{col}' type '{df[col].dtype}' not supported or classified. Supported dtypes: {[dtype for dtype in dtype_list_is_numeric]}"
            )

    # Check Graphing Settings
    if (
        not column_is_numeric_dict.get(x) and graph_settings.x_in_num
    ):  # Check x as numeric
        try:
            df[x] = pd.to_numeric(df[x])
            column_is_numeric_dict[x] = True
        except ValueError as e:
            raise ValueError(
                f"Only numeric x-values allowed for '{graph}' graphs; could not convert '{x}' to numeric."
            ) from e

    if not y and graph_settings.y_mandatory:
        raise ValueError(  # Check y mandatory
            f"For '{graph}' graphs, y-values are mandatory. Please enter column for y."
        )

    if y and graph_settings.y_accepted is False:  # Check y accepted
        readout.warn(
            f"Warning: y-values not accepted for {graph} graphs. Ignorning  y='{y}'."
        )

    if x_agg and not graph_settings.x_agg_mode:  # Check x_agg accepted
        readout.warn(
            f"X-value aggregation not accepted for '{graph}' graphs. Igorning x_agg={x_agg}."
        )
        x_agg = None

    if y_agg and not graph_settings.y_agg:  # Check y_agg accepted
        readout.warn(
            f"Y-value aggregation not accepted for '{graph}' graphs. Igorning y_agg='{y_agg}'."
        )
        y_agg = None

    # Check aggregations supported
    if type(x_agg) in (int, float):
        if df[x].dtype == "datetime64[ns]":
            raise ValueError(
                f"Numeric x_agg value ({x_agg}) used for '{df[x].dtype}' column '{x}'. Please aggregate by time period: {[t for t in x_aggs_supported_date]}"
            )
        elif not column_is_numeric_dict.get(x):
            try:
                df[x] = pd.to_numeric(df[x])
            except ValueError as e:
                raise ValueError(
                    f"Numeric x_agg value ({x_agg}) used for '{df[x].dtype}' column {x}, and column could not be converted to numeric."
                ) from e

    if x_agg in x_aggs_supported_date:
        if df[x].dtype != "datetime64[ns]":
            raise ValueError(
                f"Datetype x_agg value ('{x_agg}') used for '{df[x].dtype}' column '{x}'. Please convert or try numeric value for x_agg."
            )

    if y_agg and y_agg not in y_aggs_supported:
        raise ValueError(
            f"Unknown y_agg command '{y_agg}' received. Supported: {[c for c in y_aggs_supported]}"
        )

    if graph_settings.y_agg is False and graph_settings.x_agg_mode not in (
        "replace",
        False,
    ):
        raise ValueError(
            "Error in graph settings (if y_agg is not allowed, x_agg_mode must be None or 'replace'). Raise with developer."
        )

    # Check Optional Group
    if "colour" not in graph_settings.groups_supported:
        readout.warn(
            f"Colour grouping not supported for '{graph}' graphs. Ignorning group_colour={group_colour}"
        )
        group_colour = None

    # Handle duplicate groups
    colour_on = None
    if group_colour in [x, y]:
        colour_on = x if group_colour == x else y if group_colour == y else None
        (
            optional_columns.remove(group_colour)  # type: ignore[arg-type]
            if optional_columns and group_colour in optional_columns
            else None
        )
        (
            group_columns.remove(group_colour)  # type: ignore[arg-type]
            if group_columns and group_colour in group_colour  # type: ignore[operator]
            else None
        )
        group_colour = None

    # Aggregate DataFrame
    if graph_settings.x_agg_mode:
        all_group_columns = [x] + [col for col in group_columns if col and col != x]
        if graph_settings.y_agg:
            y_agg = "count" if not y_agg else y_agg

        # Handle duplicate x, y
        if x == y:
            new_y = f"{y}_y"
            df[new_y] = df[y]
            y = new_y

        # Create y column if does not exist
        if not y:
            if graph_settings.x_agg_mode == "replace":
                y = x
            else:
                y = f"{y_agg}_of_{x}"
                df[y] = df[x]
        else:
            if graph_settings.x_agg_mode == "replace":
                y = y
            else:
                new_y = f"{y_agg}_of_{y}"
                df.rename(columns={y: new_y}, inplace=True)
                y = new_y

        # Aggregate by Replacement
        if graph_settings.x_agg_mode == "replace":
            if df[x].dtype == "datetime64[ns]" and x_agg:
                if graph_settings.x_agg_mode == "replace":
                    df[x] = (
                        df[x]
                        .dt.to_period(x_aggs_supported_date.get(x_agg))
                        .dt.to_timestamp("s")
                    )

            elif type(x_agg) in (int, float) and column_is_numeric_dict.get(x) is True:
                df[x] = pd.cut(  # type: ignore[call-overload]
                    df[x],
                    bins=np.arange(0, df[x].max() + x_agg + 1, x_agg),
                    right=False,
                )

        # Aggregate y with no x_agg
        elif x_agg is None:
            df = (
                df.groupby(all_group_columns)
                .agg({y: lambda values: aggregate_y(y_agg, values)})  # type: ignore[arg-type]
                .reset_index()
            )

        # Aggregate x dates
        elif df[x].dtype == "datetime64[ns]":
            df = (
                df.groupby(
                    [
                        df[x]
                        .dt.to_period(x_aggs_supported_date.get(x_agg))
                        .dt.to_timestamp("s")
                    ]
                    + group_columns
                )
                .agg({y: lambda values: aggregate_y(y_agg, values)})  # type: ignore[arg-type]
                .reset_index()
            )

        # Aggregate numerics
        elif type(x_agg) in (int, float) and column_is_numeric_dict.get(x) is True:
            df = (
                df.groupby(
                    [
                        pd.cut(  # type: ignore[call-overload]
                            df[x],
                            bins=np.arange(0, df[x].max() + x_agg + 1, x_agg),
                            right=False,
                        )
                    ]
                    + group_columns,
                    observed=False,
                )
                .agg({y: lambda values: aggregate_y(y_agg, values)})  # type: ignore[arg-type]
                .reset_index()
            )

        if graph_settings.x_agg_mode == "numeric":
            df[x] = df[x].apply(lambda interval: interval.mid)

        if discard_null_aggs:
            df = df[df[y].notna()]

    else:
        pass

    df_pre_plot = df.copy()

    # Convert X Categories to str:
    if df[x].dtype == "category" and convert_categories_to_str:
        df[x] = df[x].astype(str)

    if graph_mode:
        title = (
            title
            if title
            else (
                f"{graph.capitalize()} Plot: {pretty_label(x)} vs {pretty_label(y)}"  # type: ignore[union-attr]
                if y
                else f"{graph.capitalize()} Plot: {pretty_label(x)}"  # type: ignore[union-attr]
            )
        )

        sns.set(style="darkgrid", rc={"figure.figsize": figsize})

        if group_colour:
            ncol = 1 if len(df[group_colour].unique()) <= 14 else 2
            plt.legend(
                df[group_colour].unique(),
                bbox_to_anchor=(1.0, 1.0),
                loc="upper left",
                ncol=ncol,
                title=pretty_label(group_colour),
            )

        if graph == "density":
            graph_density(
                df, x, y, group_colour=group_colour, bw_adjust=bw_adjust, alpha=alpha
            )

        if graph == "bar":
            graph_bar(
                df, x, y, group_colour=group_colour, colour_on=colour_on, alpha=alpha
            )

        if graph == "box":
            graph_box(
                df,
                x,
                y,
                group_colour=group_colour,
                colour_on=colour_on,
                showfliers=showfliers,
            )

        if graph == "violin":
            graph_violin(
                df, x, y, group_colour=group_colour, colour_on=colour_on, alpha=alpha
            )

        if graph == "scatter":
            graph_scatter(
                df,
                x,
                y,
                group_colour=group_colour,
                colour_on=colour_on,
                alpha=alpha,
                lr=linear_regression,
            )

        if graph == "stacked":
            if not group_colour:
                readout.warn(
                    "Note: stacked charts require the variable 'group_colour' - reverting to 'bar' graph"
                )
                graph_bar(
                    df,
                    x,
                    y,
                    group_colour=group_colour,
                    colour_on=colour_on,
                    alpha=alpha,
                )
            else:
                graph_stacked(
                    df,
                    x,
                    y,
                    group_colour=group_colour,
                    colour_on=colour_on,
                    alpha=alpha,
                )

        if df[x].dtype == "datetime64[ns]":
            plt.gca().xaxis.set_major_formatter(DateFormatter("%d %b %Y"))
        if df_pre_plot[x].dtype == "datetime64[ns]":
            plt.xticks(rotation=45)

        plt.title(title, fontsize=16, fontweight="bold")

        if x_label:
            plt.xlabel(x_label)

        if y_label:
            plt.ylabel(y_label)

        plt.show()
        plt.clf()
        sns.reset_orig()

    if return_results:
        return df_pre_plot
    return None
