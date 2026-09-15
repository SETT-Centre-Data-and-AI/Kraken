import math
from numbers import Integral, Real
from typing import cast

import numpy as np
import pandas as pd
from pandas import DataFrame, Series
from pandasql import sqldf  # type: ignore[import-untyped]
from scipy.stats import t as student_t  # type: ignore[import-untyped]

from kraken.exceptions import (
    GraphAggregationError,
    GraphCapabilityError,
    GraphColumnError,
    GraphConversionError,
    GraphDataError,
    GraphDataTypeError,
    GraphRenderingError,
    TimelineDataError,
)
from kraken.graphing.graphing_support_lists import (
    graph_list,
    x_aggs_supported_date,
    y_aggs_supported,
)
from kraken.graphing.models import AxisDomain, GraphSettings, GraphType, PreparedGraph
from kraken.support.readout import readout


def _initialise_graph_dataframe(
    df: DataFrame, where_clause: str | None = None
) -> DataFrame:
    """Initialises Result's dataframe with where_clause if applicable

    Args:
        df (Result | Result): DataFrame or Result containing DataFrame
        where_clause (str, optional): SQL-style where clause to apply to DataFrame. Defaults to None.

    Raises:
        GraphDataError: If no rows remain available for graphing.

    Returns:
        DataFrame: DataFrame
    """
    if not isinstance(df, DataFrame):
        df = df.df

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
        raise GraphDataError("No rows in DataFrame available for graphing")

    return df


def aggregate_y(y_agg: str, values: DataFrame | Series) -> object:
    """Applies y-aggregate calculation

    Args:
        y_agg (str): Aggregation calculation
        values: Column values

    Returns:
        Column values
    """
    result: object
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
        raise GraphAggregationError(
            f"Aggregate '{y_agg}' not recognised. Supported values are "
            f"{sorted(y_aggs_supported)}."
        )
    return result


def _numeric_bin_edges(values: Series, width: Real) -> list[int | float]:
    if isinstance(width, bool) or not math.isfinite(width) or width <= 0:
        raise GraphAggregationError(
            "Numeric x_agg must be an int or float with a finite value greater than zero"
        )

    finite_values = pd.to_numeric(values.dropna(), errors="coerce")
    if len(finite_values) == 0 or not np.isfinite(finite_values).all():
        raise GraphAggregationError(
            "Numeric x_agg requires at least one finite x value and does not accept infinite values"
        )

    numeric_width: int | float = (
        int(width) if isinstance(width, Integral) else float(width)
    )
    minimum = float(finite_values.min())
    maximum = float(finite_values.max())
    lower = math.floor(minimum / numeric_width) * numeric_width
    upper = (math.floor(maximum / numeric_width) + 1) * numeric_width
    count = math.ceil((upper - lower) / numeric_width)
    return [lower + index * numeric_width for index in range(count + 1)]


def _is_real_numeric(series: Series) -> bool:
    return pd.api.types.is_any_real_numeric_dtype(series.dtype)


def _is_quantitative(series: Series) -> bool:
    return _is_real_numeric(series) or pd.api.types.is_timedelta64_dtype(series.dtype)


def _is_temporal(series: Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(series.dtype)


def _warn_dtype_conversion(column: str, old_dtype: object, new_dtype: object) -> None:
    readout.warn(
        f"Note: graph column '{column}' converted from '{old_dtype}' to '{new_dtype}'"
    )


def _assign_converted(
    df: DataFrame, column: str, converted: Series, old_dtype: object
) -> None:
    df[column] = converted
    if str(old_dtype) != str(df[column].dtype):
        _warn_dtype_conversion(column, old_dtype, df[column].dtype)


def _coerce_real_numeric_column(
    df: DataFrame, column: str, *, graph_type: GraphType, role: str
) -> None:
    values = df[column]
    if _is_real_numeric(values):
        return
    if (
        pd.api.types.is_bool_dtype(values.dtype)
        or pd.api.types.is_complex_dtype(values.dtype)
        or _is_temporal(values)
        or pd.api.types.is_timedelta64_dtype(values.dtype)
    ):
        raise GraphDataTypeError(
            f"Graph '{graph_type}' requires real numeric {role} values in column "
            f"'{column}'; received dtype '{values.dtype}'. Accepted dtypes are "
            "real int or float values."
        )
    old_dtype = values.dtype
    try:
        converted = pd.to_numeric(values, errors="raise")
    except (TypeError, ValueError) as exc:
        raise GraphConversionError(
            f"Graph '{graph_type}' could not convert {role} column '{column}' "
            "to real numeric values. Accepted dtypes are real int or float values."
        ) from exc
    if not _is_real_numeric(converted):
        raise GraphDataTypeError(
            f"Graph '{graph_type}' requires real numeric {role} values in column "
            f"'{column}'; conversion produced dtype '{converted.dtype}'. Accepted "
            "dtypes are real int or float values."
        )
    _assign_converted(df, column, converted, old_dtype)


def _coerce_axis_column(
    df: DataFrame,
    column: str,
    *,
    graph_type: GraphType,
    role: str,
    domain: AxisDomain,
    convert_dates: bool,
) -> None:
    if domain == "any":
        return

    values = df[column]
    if domain == "temporal":
        if _is_temporal(values):
            return
        if not convert_dates:
            raise GraphDataTypeError(
                f"Graph '{graph_type}' requires datetime {role} values in column "
                f"'{column}'; received dtype '{values.dtype}' while convert_dates=False. "
                "Accepted dtypes are datetime values."
            )
        old_dtype = values.dtype
        try:
            converted = pd.to_datetime(values, errors="raise")
        except (TypeError, ValueError) as exc:
            raise GraphConversionError(
                f"Graph '{graph_type}' could not convert {role} column '{column}' "
                "to datetime values. Accepted dtypes are datetime values or "
                "datetime-convertible strings."
            ) from exc
        if not _is_temporal(converted):
            raise GraphConversionError(
                f"Graph '{graph_type}' could not convert {role} column '{column}' "
                "to one consistent datetime dtype. Use values with compatible timezones."
            )
        _assign_converted(df, column, converted, old_dtype)
        return

    if domain == "quantitative_or_temporal" and _is_temporal(values):
        return
    if domain == "quantitative" and _is_temporal(values):
        raise GraphDataTypeError(
            f"Graph '{graph_type}' requires quantitative {role} values in column "
            f"'{column}'; received datetime dtype '{values.dtype}'. Accepted dtypes "
            "are real int, float, or timedelta values."
        )
    if _is_quantitative(values):
        return
    if pd.api.types.is_bool_dtype(values.dtype) or pd.api.types.is_complex_dtype(
        values.dtype
    ):
        raise GraphDataTypeError(
            f"Graph '{graph_type}' requires quantitative {role} values in column "
            f"'{column}'; received dtype '{values.dtype}'. Accepted dtypes are real "
            "int, float, or timedelta values"
            + (", plus datetime values" if domain == "quantitative_or_temporal" else "")
            + "."
        )

    old_dtype = values.dtype
    numeric_error: BaseException | None = None
    try:
        converted = pd.to_numeric(values, errors="raise")
        if _is_real_numeric(converted):
            _assign_converted(df, column, converted, old_dtype)
            return
    except (TypeError, ValueError) as exc:
        numeric_error = exc

    try:
        converted_timedelta = pd.to_timedelta(values, errors="raise")
    except (TypeError, ValueError) as exc:
        accepted = "real int, float, or timedelta values"
        if domain == "quantitative_or_temporal":
            accepted += ", plus recognised datetime values"
        raise GraphConversionError(
            f"Graph '{graph_type}' could not convert {role} column '{column}' to a "
            f"supported quantitative dtype. Accepted dtypes are {accepted}."
        ) from (numeric_error or exc)
    if not pd.api.types.is_timedelta64_dtype(converted_timedelta.dtype):
        raise GraphConversionError(
            f"Graph '{graph_type}' could not convert {role} column '{column}' to a "
            "consistent timedelta dtype."
        )
    _assign_converted(df, column, converted_timedelta, old_dtype)


def _date_period_start(values: Series, period: str) -> Series:
    timezone = values.dt.tz
    local_values = values.dt.tz_localize(None) if timezone is not None else values
    starts = local_values.dt.to_period(x_aggs_supported_date[period]).dt.to_timestamp(
        "s"
    )
    if timezone is not None:
        daylight_saving_flags = values.map(
            lambda value: bool(value.dst()) if pd.notna(value) else False
        ).to_numpy(dtype=bool)
        starts = starts.dt.tz_localize(
            timezone,
            ambiguous=daylight_saving_flags,
            nonexistent="shift_forward",
        )
    return cast(Series, starts)


def _attach_confidence_intervals(
    prepared_df: DataFrame,
    interval_input: DataFrame,
    x: str,
    y: str,
    group_columns: list[str],
    x_agg: str | int | float | None,
    confidence_level: float,
) -> DataFrame:
    source = interval_input.copy()
    if isinstance(x_agg, str) and x_agg in x_aggs_supported_date:
        source[x] = _date_period_start(source[x], x_agg)
    elif isinstance(x_agg, Real) and not isinstance(x_agg, bool):
        source[x] = pd.cut(
            source[x],
            bins=_numeric_bin_edges(source[x], x_agg),
            right=False,
        )

    keys = [x, *group_columns]
    stats = (
        source.groupby(keys, observed=True, dropna=False, sort=False)["_interval_value"]
        .agg(count="count", mean="mean", std="std")
        .reset_index()
    )
    degrees_of_freedom = stats["count"] - 1
    standard_error = stats["std"] / np.sqrt(stats["count"])
    margin = standard_error * student_t.ppf(
        (1 + confidence_level) / 2, degrees_of_freedom
    )
    lower = stats["mean"] - margin
    upper = stats["mean"] + margin
    stats[f"lower_ci_of_{y}"] = lower
    stats[f"upper_ci_of_{y}"] = upper
    stats[f"error_plus_of_{y}"] = upper - stats["mean"]
    stats[f"error_minus_of_{y}"] = stats["mean"] - lower
    return prepared_df.merge(stats, on=keys, how="left")


def _validate_graph_capabilities(
    graph_type: GraphType,
    settings: GraphSettings,
    *,
    x: str,
    x_end: str | None,
    y: str | None,
    x_agg: str | int | float | None,
    y_agg: str | None,
    group_colour: str | None,
    facet_row: str | None,
    facet_col: str | None,
    marginal_x: str | None,
    marginal_y: str | None,
    hover_columns: list[str] | None,
    error: str | None,
    confidence_level: float,
    linear_regression: bool,
) -> tuple[str | None, bool]:
    if graph_type == "timeline":
        if x_end is None:
            raise GraphColumnError(
                "Graph 'timeline' requires an x_end column but received x_end=None. "
                "Provide an existing column containing datetime end values."
            )
    elif x_end is not None:
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received x_end='{x_end}' but does not support "
            "x_end. Accepted value is None."
        )

    if (facet_row is not None or facet_col is not None) and not settings.facets:
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received facet_row={facet_row!r} and "
            f"facet_col={facet_col!r} but does not support facets. Accepted values "
            "are None."
        )
    if (marginal_x is not None or marginal_y is not None) and not settings.marginals:
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received marginal_x={marginal_x!r} and "
            f"marginal_y={marginal_y!r} but does not support marginal plots. "
            "Accepted values are None."
        )

    axis_columns = {column for column in (x, x_end, y) if column is not None}
    for role, column in (("facet_row", facet_row), ("facet_col", facet_col)):
        if column in axis_columns:
            raise GraphColumnError(
                f"Graph '{graph_type}' {role} cannot reuse axis column '{column}'. "
                "Use a different existing column or None."
            )
    if facet_row is not None and facet_row == facet_col:
        raise GraphColumnError(
            f"Graph '{graph_type}' received facet_row=facet_col='{facet_row}'. "
            "facet_row and facet_col must use different columns, or set one to None."
        )

    requested_hover = tuple(dict.fromkeys(hover_columns or ()))
    if requested_hover and settings.hover == "none":
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received hover_columns={list(requested_hover)!r} "
            "but does not support hover_columns. Accepted value is None."
        )
    if requested_hover and settings.hover == "group":
        retained_columns = {
            column
            for column in (x, group_colour, facet_row, facet_col)
            if column is not None
        }
        unsupported_hover = [
            column for column in requested_hover if column not in retained_columns
        ]
        if unsupported_hover:
            raise GraphCapabilityError(
                f"Graph '{graph_type}' aggregates rows; hover_columns must be "
                "x, group_colour, facet_row, or facet_col columns retained after "
                f"aggregation. Unsupported: {unsupported_hover}"
            )

    if error not in (None, "confidence_interval", "ci"):
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received error={error!r}. Accepted values are "
            "'confidence_interval', 'ci', or None."
        )
    normalized_error = "confidence_interval" if error is not None else None
    if normalized_error and settings.confidence_intervals == "none":
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received error={error!r} but does not support "
            "confidence intervals. Accepted value is None."
        )
    if normalized_error and y is None:
        raise GraphColumnError(
            f"Graph '{graph_type}' confidence intervals received y=None. Provide "
            "an existing quantitative y column."
        )
    if normalized_error and y_agg != "mean":
        raise GraphAggregationError(
            f"Graph '{graph_type}' confidence intervals received y_agg={y_agg!r}. "
            "Accepted value is 'mean'."
        )
    if normalized_error and (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, Real)
        or not math.isfinite(confidence_level)
        or not 0 < confidence_level < 1
    ):
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received confidence_level={confidence_level!r}. "
            "Accepted values are finite real numbers strictly between 0 and 1."
        )

    if y is not None and settings.y_domain is None:
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received y='{y}' but does not support a y "
            "column. Accepted value is None."
        )
    if x_agg is not None and not settings.x_agg_mode:
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received x_agg={x_agg!r} but does not support "
            "x_agg. Accepted value is None."
        )
    if y_agg is not None and not settings.y_agg:
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received y_agg={y_agg!r} but does not support "
            "y_agg. Accepted value is None."
        )
    if group_colour is not None and "colour" not in settings.groups_supported:
        raise GraphCapabilityError(
            f"Graph '{graph_type}' received group_colour='{group_colour}' but does "
            "not support colour groups. Accepted value is None."
        )

    if linear_regression and not settings.regression:
        readout.warn(
            f"Note: linear_regression does not apply to graph '{graph_type}' and will be ignored"
        )
    effective_regression = settings.regression and linear_regression
    return normalized_error, effective_regression


def _validate_x_agg(
    prepared_df: DataFrame,
    x: str,
    x_agg: str | int | float | None,
    graph_type: GraphType,
) -> None:
    if x_agg is None:
        return
    if isinstance(x_agg, str):
        if x_agg not in x_aggs_supported_date:
            raise GraphAggregationError(
                f"Graph '{graph_type}' received unknown x_agg '{x_agg}'. Accepted "
                f"date periods are {list(x_aggs_supported_date)}, or use a positive "
                "int/float numeric bin width."
            )
        if not _is_temporal(prepared_df[x]):
            raise GraphAggregationError(
                f"Graph '{graph_type}' requires datetime x column '{x}' for "
                f"x_agg='{x_agg}'; received dtype '{prepared_df[x].dtype}'. Accepted "
                f"date periods are {list(x_aggs_supported_date)}."
            )
        return
    if isinstance(x_agg, bool) or not isinstance(x_agg, Real):
        raise GraphAggregationError(
            f"Graph '{graph_type}' received x_agg={x_agg!r}. Accepted values are "
            f"date periods {list(x_aggs_supported_date)} or a positive int/float."
        )
    if not math.isfinite(x_agg) or x_agg <= 0:
        raise GraphAggregationError(
            f"Graph '{graph_type}' requires a finite positive int/float x_agg; "
            f"received {x_agg!r}."
        )
    if _is_temporal(prepared_df[x]):
        raise GraphAggregationError(
            f"Graph '{graph_type}' cannot use numeric x_agg={x_agg!r} with datetime "
            f"column '{x}'. Accepted date periods are {list(x_aggs_supported_date)}."
        )
    if pd.api.types.is_timedelta64_dtype(prepared_df[x].dtype):
        raise GraphAggregationError(
            f"Graph '{graph_type}' cannot use numeric x_agg={x_agg!r} with timedelta "
            f"column '{x}' because the bin unit would be ambiguous. Accepted "
            "x_agg value for timedelta columns is None."
        )
    _coerce_real_numeric_column(
        prepared_df, x, graph_type=graph_type, role="x-axis binning"
    )


def _prepare_timeline_rows(
    prepared_df: DataFrame,
    x: str,
    x_end: str,
    *,
    discard_null_aggs: bool,
) -> DataFrame:
    missing = prepared_df[[x, x_end]].isna().any(axis=1)
    missing_count = int(missing.sum())
    if missing_count:
        if not discard_null_aggs:
            raise TimelineDataError(
                f"Graph 'timeline' found {missing_count} row(s) with missing start/end "
                "values. Set discard_null_aggs=True to discard these rows."
            )
        readout.warn(
            f"Note: graph 'timeline' discarded {missing_count} row(s) with missing "
            "start/end values"
        )
        prepared_df = prepared_df.loc[~missing].copy()
    if prepared_df.empty:
        raise TimelineDataError(
            "Graph 'timeline' has no usable rows after removing missing start/end values"
        )
    try:
        reversed_rows = prepared_df[x_end] < prepared_df[x]
    except TypeError as exc:
        raise TimelineDataError(
            f"Graph 'timeline' requires compatible datetime values in start column "
            f"'{x}' and end column '{x_end}'."
        ) from exc
    if reversed_rows.any():
        invalid_indices = prepared_df.index[reversed_rows].tolist()
        raise TimelineDataError(
            f"Graph 'timeline' found x_end values before x values at row indices "
            f"{invalid_indices}. End values must be equal to or later than start values."
        )
    return prepared_df


def prepare_graph(
    df: DataFrame,
    x: str,
    x_end: str | None = None,
    y: str | None = None,
    facet_row: str | None = None,
    facet_col: str | None = None,
    marginal_x: str | None = None,
    marginal_y: str | None = None,
    hover_columns: list[str] | None = None,
    linear_regression: bool = False,
    error: str | None = None,
    confidence_level: float = 0.95,
    graph_type: str | None = None,
    x_agg: str | int | float | None = None,
    y_agg: str | None = None,
    group_colour: str | None = None,
    where_clause: str | None = None,
    convert_dates: bool = True,
    discard_null_aggs: bool = True,
    convert_categories_to_str: bool = False,
) -> PreparedGraph:
    from kraken.analysis.data_manipulation import date_converter_df

    prepared_df = _initialise_graph_dataframe(df, where_clause=where_clause)
    input_columns = list(prepared_df.columns)

    if graph_type is not None and not isinstance(graph_type, str):
        raise GraphCapabilityError(
            f"Graph name received {graph_type!r} ({type(graph_type).__name__}). "
            f"Accepted values are None or one of {list(graph_list)}."
        )
    requested_graph = graph_type.lower() if graph_type else "aggregation"
    if requested_graph not in graph_list:
        raise GraphCapabilityError(
            f"Graph '{requested_graph}' not supported. Supported graphs: "
            f"{list(graph_list)}"
        )
    resolved_graph = cast(GraphType, requested_graph)
    graph_settings = graph_list[resolved_graph]
    graph_mode = resolved_graph != "aggregation"
    x_agg = x_agg.lower() if isinstance(x_agg, str) else x_agg
    if y_agg is not None and not isinstance(y_agg, str):
        raise GraphAggregationError(
            f"y_agg must be a string or None; received {type(y_agg).__name__}. "
            f"Supported values are {sorted(y_aggs_supported)}."
        )
    y_agg = y_agg.lower() if y_agg else y_agg
    requested_y_agg = y_agg
    error, effective_regression = _validate_graph_capabilities(
        resolved_graph,
        graph_settings,
        x=x,
        x_end=x_end,
        y=y,
        x_agg=x_agg,
        y_agg=y_agg,
        group_colour=group_colour,
        facet_row=facet_row,
        facet_col=facet_col,
        marginal_x=marginal_x,
        marginal_y=marginal_y,
        hover_columns=hover_columns,
        error=error,
        confidence_level=confidence_level,
        linear_regression=linear_regression,
    )
    hover_columns = list(dict.fromkeys(hover_columns or ()))

    if y is None and graph_settings.y_mandatory:
        raise GraphColumnError(
            f"Graph '{resolved_graph}' received y=None; y-values are mandatory. "
            f"Provide one of the existing columns {input_columns}."
        )

    selected_columns = list(
        dict.fromkeys(
            column for column in (x, x_end, y, group_colour) if column is not None
        )
    )
    modifier_columns = [
        column
        for column in (facet_row, facet_col, *(hover_columns or []))
        if column is not None
    ]
    selected_columns = list(dict.fromkeys([*selected_columns, *modifier_columns]))

    for column in selected_columns:
        if column not in input_columns:
            raise GraphColumnError(
                f"Graph '{resolved_graph}' column '{column}' was not found in the DataFrame. "
                f"Available columns are {input_columns}."
            )

    if graph_type is None:
        readout.warn(
            f"Note: no graph selected - aggregating data only. Supported graphs: {[name for name in graph_list]}"
        )

    prepared_df = prepared_df.loc[:, selected_columns].copy()
    if convert_dates:
        original_dtypes = prepared_df.dtypes.to_dict()
        prepared_df = date_converter_df(prepared_df, selected_columns, readouts=False)
        for column, old_dtype in original_dtypes.items():
            if str(old_dtype) != str(prepared_df[column].dtype):
                _warn_dtype_conversion(column, old_dtype, prepared_df[column].dtype)

    _coerce_axis_column(
        prepared_df,
        x,
        graph_type=resolved_graph,
        role="x-axis",
        domain=graph_settings.x_domain,
        convert_dates=convert_dates,
    )
    if x_end is not None:
        _coerce_axis_column(
            prepared_df,
            x_end,
            graph_type=resolved_graph,
            role="x_end",
            domain="temporal",
            convert_dates=convert_dates,
        )
    if y is not None and graph_settings.y_domain is not None:
        _coerce_axis_column(
            prepared_df,
            y,
            graph_type=resolved_graph,
            role="y-axis",
            domain=graph_settings.y_domain,
            convert_dates=convert_dates,
        )

    if resolved_graph == "timeline" and x_end is not None:
        prepared_df = _prepare_timeline_rows(
            prepared_df,
            x,
            x_end,
            discard_null_aggs=discard_null_aggs,
        )

    if y_agg and y_agg not in y_aggs_supported:
        raise GraphAggregationError(
            f"Unknown y_agg '{y_agg}' received for graph '{resolved_graph}'. "
            f"Supported values are {sorted(y_aggs_supported)}."
        )

    _validate_x_agg(prepared_df, x, x_agg, resolved_graph)

    if not graph_settings.y_agg and graph_settings.x_agg_mode not in ("replace", False):
        raise GraphRenderingError(
            "Error in graph settings (if y_agg is not allowed, x_agg_mode must be None or 'replace'). Raise with developer."
        )

    aggregate_rows = bool(
        graph_settings.x_agg_mode and graph_settings.x_agg_mode != "replace"
    )
    colour_on: str | None = None
    if group_colour == x or (group_colour == y and not aggregate_rows):
        colour_on = group_colour
        group_colour = None

    group_columns = [group_colour] if group_colour else []
    group_columns.extend(
        column
        for column in (facet_row, facet_col)
        if column and column not in group_columns
    )
    interval_input: DataFrame | None = None

    if graph_settings.x_agg_mode:
        if graph_settings.x_agg_mode == "replace":
            if isinstance(x_agg, str):
                prepared_df[x] = _date_period_start(prepared_df[x], x_agg)
            elif isinstance(x_agg, Real) and not isinstance(x_agg, bool):
                prepared_df[x] = pd.cut(
                    prepared_df[x],
                    bins=_numeric_bin_edges(prepared_df[x], x_agg),
                    right=False,
                )
            if discard_null_aggs and y:
                prepared_df = prepared_df[prepared_df[y].notna()]
        else:
            effective_y_agg = y_agg or "count"
            if resolved_graph == "histogram" and requested_y_agg in {
                "sum",
                "mean",
                "mode",
                "median",
            }:
                readout.warn(
                    f"Note: histogram y_agg='{requested_y_agg}' aggregates x values; "
                    "a bar chart may present this measure more clearly"
                )

            measure_column = y or x
            if effective_y_agg in {"sum", "mean", "median"}:
                _coerce_axis_column(
                    prepared_df,
                    measure_column,
                    graph_type=resolved_graph,
                    role=f"{effective_y_agg} measure",
                    domain="quantitative",
                    convert_dates=convert_dates,
                )

            measure_label = (
                f"{measure_column}_y" if y is not None and x == y else measure_column
            )
            aggregated_y = f"{effective_y_agg}_of_{measure_label}"
            prepared_df[aggregated_y] = prepared_df[measure_column]
            y = aggregated_y

            if error:
                interval_input = prepared_df[[x, *group_columns]].copy()
                interval_input["_interval_value"] = prepared_df[y]

            prepared_df = prepared_df[prepared_df[x].notna()]
            if interval_input is not None:
                interval_input = interval_input[interval_input[x].notna()]

            if x_agg is None:
                group_values: list[Series | str] = [x, *group_columns]
            elif isinstance(x_agg, str):
                group_values = [
                    _date_period_start(prepared_df[x], x_agg),
                    *group_columns,
                ]
            else:
                group_values = [
                    pd.cut(
                        prepared_df[x],
                        bins=_numeric_bin_edges(prepared_df[x], cast(Real, x_agg)),
                        right=False,
                    ),
                    *group_columns,
                ]

            prepared_df = (
                prepared_df.groupby(
                    group_values,
                    observed=False,
                    dropna=False,
                    sort=False,
                )
                .agg({y: lambda values: aggregate_y(effective_y_agg, values)})
                .reset_index()
            )

            if discard_null_aggs and y:
                prepared_df = prepared_df[prepared_df[y].notna()]

            if error and interval_input is not None:
                prepared_df = _attach_confidence_intervals(
                    prepared_df,
                    interval_input,
                    x,
                    y,
                    group_columns,
                    x_agg,
                    confidence_level,
                )

            # Keep interval keys until confidence-interval statistics have been
            # attached; numeric renderers can use their midpoints afterward.
            if (
                graph_settings.x_agg_mode == "numeric"
                and isinstance(x_agg, Real)
                and not isinstance(x_agg, bool)
                and len(prepared_df[x]) > 0
                and isinstance(prepared_df[x].iloc[0], pd.Interval)
            ):
                prepared_df[x] = pd.to_numeric(
                    prepared_df[x].astype(object).map(lambda interval: interval.mid)
                )

    result_data = prepared_df.copy()
    plot_data = prepared_df.copy()
    if plot_data[x].dtype == "category" and convert_categories_to_str:
        plot_data[x] = plot_data[x].astype(str)

    error_columns = (
        {
            "lower": f"lower_ci_of_{y}",
            "upper": f"upper_ci_of_{y}",
            "plus": f"error_plus_of_{y}",
            "minus": f"error_minus_of_{y}",
        }
        if error and y
        else {}
    )
    effective_error = (
        error
        if all(column in result_data.columns for column in error_columns.values())
        else None
    )
    missing_hover_columns = [
        column for column in hover_columns if column not in result_data.columns
    ]
    if missing_hover_columns:
        raise GraphRenderingError(
            f"hover_columns were not retained in prepared data: {missing_hover_columns}"
        )

    return PreparedGraph(
        data=result_data,
        plot_data=plot_data,
        graph_type=resolved_graph,
        graph_mode=graph_mode,
        settings=graph_settings,
        x=x,
        x_end=x_end,
        y=y,
        group_colour=group_colour,
        colour_on=colour_on,
        facet_row=facet_row,
        facet_col=facet_col,
        marginal_x=marginal_x,
        marginal_y=marginal_y,
        hover_columns=tuple(hover_columns),
        linear_regression=effective_regression,
        error=effective_error,
        error_lower=error_columns.get("lower") if effective_error else None,
        error_upper=error_columns.get("upper") if effective_error else None,
        error_plus=error_columns.get("plus") if effective_error else None,
        error_minus=error_columns.get("minus") if effective_error else None,
    )


def pretty_label(name: str) -> str:
    return name.replace("_", " ").lower().title()
