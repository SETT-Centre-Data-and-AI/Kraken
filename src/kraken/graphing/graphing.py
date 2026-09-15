import math
import warnings
from dataclasses import replace
from numbers import Integral, Real

import pandas as pd

from kraken.exceptions import GraphCapabilityError
from kraken.graphing.graphing_graphs import render_graph
from kraken.graphing.graphing_support import prepare_graph
from kraken.graphing.graphing_theme import graph_label
from kraken.graphing.models import GraphResult, GraphType
from kraken.support.readout import readout


def _validate_render_parameters(
    *,
    bw_adjust: float,
    alpha: float | None,
    width: int | None,
    height: int | None,
    validate_bw_adjust: bool,
) -> None:
    if validate_bw_adjust and (
        isinstance(bw_adjust, bool)
        or not isinstance(bw_adjust, Real)
        or not math.isfinite(bw_adjust)
        or bw_adjust <= 0
    ):
        raise GraphCapabilityError(
            "bw_adjust must be a finite number greater than zero for density graphs"
        )

    if alpha is not None and (
        isinstance(alpha, bool)
        or not isinstance(alpha, Real)
        or not math.isfinite(alpha)
        or not 0 <= alpha <= 1
    ):
        raise GraphCapabilityError("alpha must be a finite number between 0 and 1")

    for name, value in (("width", width), ("height", height)):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, Integral) or value < 10
        ):
            raise GraphCapabilityError(
                f"{name} must be an integer of at least 10 pixels"
            )


def graph(
    df: pd.DataFrame,
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
    """Prepare row-level data and build an interactive graph.

    Kraken validates the selected columns and graph capabilities before applying
    any requested x binning and y aggregation. The returned result always includes
    the exact prepared dataset and, for graph modes, an editable Plotly figure.

    Args:
        df: Input DataFrame or Kraken result object containing a DataFrame.
        x: X-axis column. Density, histogram, and scatter accept real numeric,
            timedelta, or datetime values; timeline requires datetime values.
        y: Optional y-axis column. Box, violin, density, and scatter require real
            numeric or timedelta values. Aggregate charts default to a count of x.
        graph: Graph type. If omitted or ``aggregation``, only data is prepared.
        x_agg: Date period (``minute``, ``hour``, ``day``, ``week``, ``month``, or
            ``year``) or a finite positive ``int``/``float`` bin width applied to x
            where supported. Numeric widths cannot bin timedeltas. Weeks run Monday
            to Sunday and are labelled by their Monday start date.
        y_agg: ``count``, ``countd``, ``sum``, ``mean``, ``mode``, or ``median``.
            If y is omitted, the aggregation is applied to a duplicate of x.
            ``sum``, ``mean``, and ``median`` require quantitative values.
        group_colour: Column used to split traces by colour.
        where_clause: SQL-style filter applied before preparation.
        convert_dates: Convert recognised date axes to datetime. Required numeric
            axes and measures are also converted automatically. Every successful
            dtype conversion emits a suppressible Kraken warning; conversion is
            all-or-nothing and retained in the returned data.
        discard_null_aggs: Remove rows with null aggregate results. For timelines,
            also discard rows missing a start or end and warn with the count. If
            false, missing timeline dates raise ``TimelineDataError``.
        figsize: Deprecated width and height in inches, converted to Plotly pixels.
        bw_adjust: Density bandwidth multiplier.
        alpha: Trace opacity.
        convert_categories_to_str: Convert categorical x values for display.
        linear_regression: Add regression lines to scatter plots. Defaults to
            false. Setting it to true on another renderer is ignored with a warning.
        showfliers: Display outliers on box plots.
        title: Figure title. Generated when omitted.
        x_label: X-axis label. Generated when omitted.
        y_label: Y-axis label. Generated when omitted.
        return_results: Deprecated compatibility argument. It has no effect;
            prepared data is always available as ``.data``.
        width: Explicit Plotly figure width in pixels, as an integer of at least 10.
            Responsive by default.
        height: Explicit Plotly figure height in pixels, as an integer of at least 10.
        scroll: Allow a wide fixed canvas for horizontal scrolling in the host output.
        show: Display the interactive figure immediately.
        x_end: End-date column required by timeline graphs.
        facet_row: Column used to create facet rows where supported.
        facet_col: Column used to create facet columns where supported.
        marginal_x: Scatter marginal renderer for x where supported.
        marginal_y: Scatter marginal renderer for y where supported.
        hover_columns: Additional row-level or grouping hover columns where supported.
        error: ``confidence_interval`` for supported mean aggregations.
        confidence_level: Confidence level strictly between zero and one.

    Returns:
        A result containing the Plotly figure and prepared DataFrame.

    Raises:
        GraphingError: If the requested graph capability, columns, dtypes,
            conversion, aggregation, input data, rendering, or export is invalid.
    """
    if return_results:
        warnings.warn(
            "return_results is deprecated and has no effect; graph() returns "
            "GraphResult and prepared data is available from result.data.",
            DeprecationWarning,
            stacklevel=2,
        )

    prepared = prepare_graph(
        df=df,
        x=x,
        x_end=x_end,
        y=y,
        facet_row=facet_row,
        facet_col=facet_col,
        marginal_x=marginal_x,
        marginal_y=marginal_y,
        hover_columns=hover_columns,
        linear_regression=linear_regression,
        error=error,
        confidence_level=confidence_level,
        graph_type=graph,
        x_agg=x_agg,
        y_agg=y_agg,
        group_colour=group_colour,
        where_clause=where_clause,
        convert_dates=convert_dates,
        discard_null_aggs=discard_null_aggs,
        convert_categories_to_str=convert_categories_to_str,
    )

    _validate_render_parameters(
        bw_adjust=bw_adjust,
        alpha=alpha,
        width=width,
        height=height,
        validate_bw_adjust=prepared.graph_type == "density",
    )
    if prepared.graph_type != "density" and bw_adjust != 0.5:
        readout.warn(
            f"Note: bw_adjust does not apply to graph '{prepared.graph_type}' and will be ignored"
        )
    if prepared.graph_type != "box" and showfliers is not True:
        readout.warn(
            f"Note: showfliers does not apply to graph '{prepared.graph_type}' and will be ignored"
        )

    if not prepared.graph_mode:
        return GraphResult(
            figure=None,
            data=prepared.data,
            graph_type=prepared.graph_type,
            x=prepared.x,
            x_end=prepared.x_end,
            y=prepared.y,
            group_colour=prepared.group_colour or prepared.colour_on,
            facet_row=prepared.facet_row,
            facet_col=prepared.facet_col,
            marginal_x=prepared.marginal_x,
            marginal_y=prepared.marginal_y,
            hover_columns=prepared.hover_columns,
            error=prepared.error,
            error_lower=prepared.error_lower,
            error_upper=prepared.error_upper,
            error_plus=prepared.error_plus,
            error_minus=prepared.error_minus,
        )

    if prepared.graph_type == "stacked" and not prepared.group_colour:
        readout.warn(
            "Note: stacked charts require the variable 'group_colour' - reverting to 'bar' graph"
        )
        render_prepared = replace(prepared, graph_type="bar")
    else:
        render_prepared = prepared

    effective_graph_type = render_prepared.graph_type
    resolved_title = title or (
        f"{effective_graph_type.capitalize()} Plot: {graph_label(prepared.x)} "
        f"vs {graph_label(prepared.y)}"
        if prepared.y
        else f"{effective_graph_type.capitalize()} Plot: {graph_label(prepared.x)}"
    )
    figure = render_graph(
        render_prepared,
        title=resolved_title,
        x_label=x_label,
        y_label=y_label,
        figsize=figsize,
        bw_adjust=bw_adjust,
        alpha=alpha,
        showfliers=showfliers,
        width=width,
        height=height,
        scroll=scroll,
    )
    if show:
        figure.show(
            config={
                "responsive": not scroll,
                "displaylogo": False,
                "toImageButtonOptions": {"scale": 2},
            }
        )

    return GraphResult(
        figure=figure,
        data=prepared.data,
        graph_type=effective_graph_type,
        x=prepared.x,
        x_end=prepared.x_end,
        y=prepared.y,
        group_colour=prepared.group_colour or prepared.colour_on,
        facet_row=prepared.facet_row,
        facet_col=prepared.facet_col,
        marginal_x=prepared.marginal_x,
        marginal_y=prepared.marginal_y,
        hover_columns=prepared.hover_columns,
        error=prepared.error,
        error_lower=prepared.error_lower,
        error_upper=prepared.error_upper,
        error_plus=prepared.error_plus,
        error_minus=prepared.error_minus,
    )
