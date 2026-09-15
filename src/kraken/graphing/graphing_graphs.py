from collections.abc import Iterable

import numpy as np
import pandas as pd
import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
from scipy.stats import gaussian_kde  # type: ignore[import-untyped]

from kraken.exceptions import (
    GraphingError,
    GraphRenderingError,
    InsufficientGraphDataError,
)
from kraken.graphing.graphing_theme import (
    KRAKEN_COLOUR_SEQUENCE,
    KRAKEN_MISSING_COLOUR,
    KRAKEN_TEMPLATE,
    apply_kraken_theme,
    colour_with_alpha,
    darken_colour,
    graph_label,
)
from kraken.graphing.models import PreparedGraph

_MISSING_GROUP_LABEL = "(Missing)"
_COLOUR_ALIAS_PREFIX = "__kraken_colour_"


def _discrete_group_values(values: pd.Series) -> pd.Series:
    normalized = values.astype(object).where(values.notna(), _MISSING_GROUP_LABEL)
    return normalized.map(str)


def _declared_x_category_order(prepared: PreparedGraph) -> tuple[str, ...]:
    values = prepared.data[prepared.x]
    if not isinstance(values.dtype, pd.CategoricalDtype):
        return ()
    categories = values.cat.categories
    if not isinstance(categories, pd.IntervalIndex):
        categories = values.cat.remove_unused_categories().cat.categories
    return tuple(str(category) for category in categories)


def _x_category_order(prepared: PreparedGraph) -> tuple[str, ...]:
    values = prepared.data[prepared.x]
    declared_order = _declared_x_category_order(prepared)
    if prepared.graph_type not in {"bar", "stacked"}:
        return declared_order

    if isinstance(values.dtype, pd.CategoricalDtype):
        if values.dtype.ordered or isinstance(values.cat.categories, pd.IntervalIndex):
            return declared_order
    elif (
        pd.api.types.is_datetime64_any_dtype(values.dtype)
        or pd.api.types.is_timedelta64_dtype(values.dtype)
        or (
            pd.api.types.is_numeric_dtype(values.dtype)
            and not pd.api.types.is_bool_dtype(values.dtype)
        )
    ):
        return ()

    display_values = tuple(dict.fromkeys(values.dropna().map(str)))
    return tuple(sorted(display_values, key=lambda value: (value.casefold(), value)))


def _plot_data(prepared: PreparedGraph) -> pd.DataFrame:
    data = prepared.plot_data.copy()
    source_hue = prepared.group_colour or prepared.colour_on
    plot_hue = _hue_column(prepared)
    if source_hue in data.columns and plot_hue is not None:
        data[plot_hue] = _discrete_group_values(data[source_hue])
    category_order = _declared_x_category_order(prepared)
    if isinstance(prepared.data[prepared.x].dtype, pd.CategoricalDtype):
        display_values = data[prepared.x].astype(str)
        if category_order:
            data[prepared.x] = pd.Categorical(
                display_values,
                categories=category_order,
                ordered=True,
            )
            data = data.sort_values(prepared.x, kind="stable")
        else:
            data[prepared.x] = display_values
    return data


def _hue_column(prepared: PreparedGraph) -> str | None:
    if prepared.colour_on is not None:
        return f"{_COLOUR_ALIAS_PREFIX}{prepared.colour_on}"
    return prepared.group_colour


def _hue(prepared: PreparedGraph, data: pd.DataFrame) -> str | None:
    hue = _hue_column(prepared)
    return hue if hue in data.columns else None


def _express_options(prepared: PreparedGraph, data: pd.DataFrame) -> dict[str, object]:
    labels = {column: graph_label(column) for column in data.columns}
    source_hue = prepared.group_colour or prepared.colour_on
    plot_hue = _hue_column(prepared)
    if source_hue is not None and plot_hue is not None:
        labels[plot_hue] = graph_label(source_hue)
    options: dict[str, object] = {
        "template": KRAKEN_TEMPLATE,
        "labels": labels,
    }
    category_order = _x_category_order(prepared)
    if category_order:
        options["category_orders"] = {prepared.x: list(category_order)}
    if prepared.facet_row is not None:
        if prepared.facet_row not in data.columns:
            raise GraphRenderingError(
                f"Prepared facet_row column '{prepared.facet_row}' is missing"
            )
        options["facet_row"] = prepared.facet_row
        options["facet_row_spacing"] = 0.06
    if prepared.facet_col is not None:
        if prepared.facet_col not in data.columns:
            raise GraphRenderingError(
                f"Prepared facet_col column '{prepared.facet_col}' is missing"
            )
        options["facet_col"] = prepared.facet_col
        options["facet_col_spacing"] = 0.04
    missing_hover_columns = [
        column for column in prepared.hover_columns if column not in data.columns
    ]
    if missing_hover_columns:
        raise GraphRenderingError(
            f"Prepared hover columns are missing: {missing_hover_columns}"
        )
    if prepared.hover_columns:
        options["hover_data"] = list(prepared.hover_columns)
    return options


def _error_options(prepared: PreparedGraph, data: pd.DataFrame) -> dict[str, object]:
    if prepared.error is None:
        return {}
    if prepared.error_plus in data.columns and prepared.error_minus in data.columns:
        return {
            "error_y": prepared.error_plus,
            "error_y_minus": prepared.error_minus,
        }
    raise GraphRenderingError("Prepared confidence-interval columns are missing")


def _groups(
    data: pd.DataFrame, hue: str | None
) -> Iterable[tuple[str | None, pd.DataFrame]]:
    if not hue:
        return [(None, data)]
    return (
        (str(name), group)
        for name, group in data.groupby(hue, dropna=False, observed=True, sort=False)
    )


def _graph_bar(prepared: PreparedGraph, alpha: float | None) -> go.Figure:
    data = _plot_data(prepared)
    return px.bar(
        data,
        x=prepared.x,
        y=prepared.y,
        color=_hue(prepared, data),
        barmode="group",
        opacity=alpha if alpha is not None else 1,
        **_express_options(prepared, data),
        **_error_options(prepared, data),
    )


def _graph_histogram(prepared: PreparedGraph, alpha: float | None) -> go.Figure:
    data = _plot_data(prepared)
    return px.bar(
        data,
        x=prepared.x,
        y=prepared.y,
        color=_hue(prepared, data),
        barmode="group",
        opacity=alpha if alpha is not None else 1,
        **_express_options(prepared, data),
        **_error_options(prepared, data),
    )


def _graph_timeline(prepared: PreparedGraph, alpha: float | None) -> go.Figure:
    if prepared.x_end is None or prepared.y is None:
        raise GraphRenderingError("Timeline graphs require x_end and y columns")
    data = _plot_data(prepared)
    return px.timeline(
        data,
        x_start=prepared.x,
        x_end=prepared.x_end,
        y=prepared.y,
        color=_hue(prepared, data),
        opacity=alpha if alpha is not None else 1,
        **_express_options(prepared, data),
    )


def _graph_stacked(prepared: PreparedGraph, alpha: float | None) -> go.Figure:
    data = _plot_data(prepared)
    return px.bar(
        data,
        x=prepared.x,
        y=prepared.y,
        color=_hue(prepared, data),
        barmode="stack",
        opacity=alpha if alpha is not None else 1,
        **_express_options(prepared, data),
    )


def _graph_box(prepared: PreparedGraph, showfliers: bool) -> go.Figure:
    data = _plot_data(prepared)
    return px.box(
        data,
        x=prepared.x,
        y=prepared.y,
        color=_hue(prepared, data),
        points="outliers" if showfliers else False,
        **_express_options(prepared, data),
    )


def _graph_violin(prepared: PreparedGraph, alpha: float | None) -> go.Figure:
    data = _plot_data(prepared)
    figure = px.violin(
        data,
        x=prepared.x,
        y=prepared.y,
        color=_hue(prepared, data),
        **_express_options(prepared, data),
    )
    figure.update_traces(opacity=alpha if alpha is not None else 1)
    return figure


def _graph_scatter(
    prepared: PreparedGraph, alpha: float | None, linear_regression: bool
) -> go.Figure:
    data = _plot_data(prepared)
    hue = _hue(prepared, data)
    figure = px.scatter(
        data,
        x=prepared.x,
        y=prepared.y,
        color=hue,
        opacity=0.72 if alpha is None else 1,
        marginal_x=prepared.marginal_x,
        marginal_y=prepared.marginal_y,
        **_express_options(prepared, data),
        **_error_options(prepared, data),
    )
    if not linear_regression or not prepared.y:
        return figure

    point_traces = tuple(
        trace
        for trace in figure.data
        if trace.type in {"scatter", "scattergl"}
        and trace.mode is not None
        and "markers" in trace.mode
    )
    for point_trace in point_traces:
        points = pd.DataFrame({"x": point_trace.x, "y": point_trace.y}).dropna()
        if len(points) < 2:
            continue

        x_values = points["x"]
        if pd.api.types.is_datetime64_any_dtype(x_values.dtype):
            regression_x = x_values.astype("int64").to_numpy(dtype=float)
            plotted_x = x_values.to_numpy()
        else:
            regression_x = pd.to_numeric(x_values, errors="coerce").to_numpy(
                dtype=float
            )
            plotted_x = regression_x

        regression_y = pd.to_numeric(points["y"], errors="coerce").to_numpy(dtype=float)
        finite = np.isfinite(regression_x) & np.isfinite(regression_y)
        if finite.sum() < 2 or np.unique(regression_x[finite]).size < 2:
            continue

        finite_x = regression_x[finite]
        finite_y = regression_y[finite]
        order = np.argsort(finite_x)
        line_numeric = finite_x[order]
        line_x = plotted_x[finite][order]
        slope, intercept = np.polyfit(finite_x, finite_y, 1)
        group_name = str(point_trace.name) if hue else None
        regression_name = (
            f"Linear regression ({group_name})" if hue else "Linear regression"
        )
        point_colour = (
            KRAKEN_MISSING_COLOUR
            if group_name == _MISSING_GROUP_LABEL
            else str(point_trace.marker.color or KRAKEN_COLOUR_SEQUENCE[0])
        )
        figure.add_trace(
            go.Scatter(
                x=line_x,
                y=slope * line_numeric + intercept,
                mode="lines",
                name=regression_name,
                line={
                    "color": darken_colour(point_colour),
                    "width": 3,
                    "dash": "solid",
                },
                opacity=1,
                zorder=10,
                xaxis=point_trace.xaxis,
                yaxis=point_trace.yaxis,
                legendgroup=point_trace.legendgroup
                or f"regression:{group_name or 'all'}",
                showlegend=False,
            )
        )
    return figure


def _numeric_density_values(series: pd.Series) -> tuple[np.ndarray, bool]:
    series = series.loc[series.notna()]
    is_datetime = pd.api.types.is_datetime64_any_dtype(series.dtype)
    values = (
        series.astype("int64").to_numpy(dtype=float)
        if is_datetime
        else pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    )
    return values[np.isfinite(values)], is_datetime


def _density_grid(values: np.ndarray, points: int = 200) -> np.ndarray:
    padding = (values.max() - values.min()) * 0.05
    return np.linspace(values.min() - padding, values.max() + padding, points)


def _graph_density(
    prepared: PreparedGraph, bw_adjust: float, alpha: float | None
) -> go.Figure:
    data = _plot_data(prepared)
    hue = _hue(prepared, data)
    figure = go.Figure(layout={"template": KRAKEN_TEMPLATE})

    for colour_index, (name, group) in enumerate(_groups(data, hue)):
        group_label = f" for colour group '{name}'" if name is not None else ""
        colour = (
            KRAKEN_MISSING_COLOUR
            if name == _MISSING_GROUP_LABEL
            else KRAKEN_COLOUR_SEQUENCE[colour_index % len(KRAKEN_COLOUR_SEQUENCE)]
        )
        x_values, x_is_datetime = _numeric_density_values(group[prepared.x])
        if x_values.size < 2 or np.unique(x_values).size < 2:
            raise InsufficientGraphDataError(
                f"Graph 'density' requires at least two finite, distinct x values"
                f"{group_label}; column '{prepared.x}' cannot produce a KDE."
            )

        if not prepared.y:
            try:
                kde = gaussian_kde(x_values)
            except (np.linalg.LinAlgError, ValueError) as exc:
                raise InsufficientGraphDataError(
                    f"Graph 'density' could not calculate a one-dimensional KDE"
                    f"{group_label}; provide more varied values in column "
                    f"'{prepared.x}'."
                ) from exc
            kde.set_bandwidth(kde.factor * bw_adjust)
            x_grid = _density_grid(x_values)
            plotted_x = pd.to_datetime(x_grid) if x_is_datetime else x_grid
            figure.add_trace(
                go.Scatter(
                    x=plotted_x,
                    y=kde(x_grid),
                    mode="lines",
                    fill="tozeroy",
                    name=name or graph_label(prepared.x),
                    legendgroup=name,
                    showlegend=hue is not None,
                    line={"color": colour, "width": 2.25},
                    fillcolor=colour_with_alpha(colour, 0.18),
                    opacity=alpha if alpha is not None else 1,
                    hovertemplate=(
                        f"{graph_label(prepared.x)}=%{{x}}<br>"
                        "Density=%{y:.3g}<extra></extra>"
                    ),
                )
            )
            continue

        paired_values = group[[prepared.x, prepared.y]].dropna()
        paired_x_series = paired_values[prepared.x]
        numeric_x = (
            paired_x_series.astype("int64").to_numpy(dtype=float)
            if x_is_datetime
            else pd.to_numeric(paired_x_series, errors="coerce").to_numpy(dtype=float)
        )
        numeric_y = pd.to_numeric(paired_values[prepared.y], errors="coerce").to_numpy(
            dtype=float
        )
        paired = np.isfinite(numeric_x) & np.isfinite(numeric_y)
        paired_x = numeric_x[paired]
        paired_y = numeric_y[paired]
        if (
            paired_x.size < 3
            or np.unique(paired_x).size < 2
            or np.unique(paired_y).size < 2
        ):
            raise InsufficientGraphDataError(
                "Graph 'density' requires at least three finite x/y pairs with two "
                f"distinct values on each axis{group_label}; columns '{prepared.x}' "
                f"and '{prepared.y}' cannot produce a KDE."
            )

        try:
            kde = gaussian_kde(np.vstack([paired_x, paired_y]))
        except (np.linalg.LinAlgError, ValueError) as exc:
            raise InsufficientGraphDataError(
                f"Graph 'density' could not calculate a two-dimensional KDE"
                f"{group_label}; provide more varied values in columns "
                f"'{prepared.x}' and '{prepared.y}'."
            ) from exc
        kde.set_bandwidth(kde.factor * bw_adjust)
        x_grid = _density_grid(paired_x, points=80)
        y_grid = _density_grid(paired_y, points=80)
        mesh_x, mesh_y = np.meshgrid(x_grid, y_grid)
        density = kde(np.vstack([mesh_x.ravel(), mesh_y.ravel()])).reshape(mesh_x.shape)
        plotted_x = pd.to_datetime(x_grid) if x_is_datetime else x_grid
        figure.add_trace(
            go.Contour(
                x=plotted_x,
                y=y_grid,
                z=density,
                name=name or "Density",
                legendgroup=name,
                showlegend=hue is not None,
                contours={"coloring": "fill", "showlines": False},
                colorscale=[
                    [0.0, colour_with_alpha(colour, 0.0)],
                    [0.2, colour_with_alpha(colour, 0.12)],
                    [1.0, colour],
                ],
                line={"color": colour, "width": 0.75},
                opacity=alpha if alpha is not None else 0.68,
                showscale=False,
                hovertemplate=(
                    f"{graph_label(prepared.x)}=%{{x}}<br>"
                    f"{graph_label(prepared.y)}=%{{y}}<br>"
                    "Density=%{z:.3g}<extra></extra>"
                ),
            )
        )

    return figure


def _graph_line(prepared: PreparedGraph) -> go.Figure:
    data = _plot_data(prepared)
    hue = _hue(prepared, data)
    sort_columns = [column for column in (hue, prepared.x) if column]
    return px.line(
        data.sort_values(sort_columns),
        x=prepared.x,
        y=prepared.y,
        color=hue,
        markers=True,
        **_express_options(prepared, data),
        **_error_options(prepared, data),
    )


def _graph_area(prepared: PreparedGraph, alpha: float | None) -> go.Figure:
    data = _plot_data(prepared)
    hue = _hue(prepared, data)
    sort_columns = [column for column in (hue, prepared.x) if column]
    figure = px.area(
        data.sort_values(sort_columns),
        x=prepared.x,
        y=prepared.y,
        color=hue,
        **_express_options(prepared, data),
    )
    for index, trace in enumerate(figure.data):
        trace.fill = "tozeroy" if index == 0 else "tonexty"
        trace.stackgroup = "area"
        trace.opacity = alpha if alpha is not None else 0.55
    return figure


def _render_prepared_graph(
    prepared: PreparedGraph,
    *,
    title: str,
    x_label: str | None,
    y_label: str | None,
    figsize: tuple[int, int] | None,
    width: int | None,
    height: int | None,
    scroll: bool,
    bw_adjust: float,
    alpha: float | None,
    showfliers: bool,
) -> go.Figure:
    if prepared.graph_type == "density":
        figure = _graph_density(prepared, bw_adjust=bw_adjust, alpha=alpha)
    elif prepared.graph_type == "histogram":
        figure = _graph_histogram(prepared, alpha=alpha)
    elif prepared.graph_type == "bar":
        figure = _graph_bar(prepared, alpha=alpha)
    elif prepared.graph_type == "stacked":
        figure = _graph_stacked(prepared, alpha=alpha)
    elif prepared.graph_type == "box":
        figure = _graph_box(prepared, showfliers=showfliers)
    elif prepared.graph_type == "violin":
        figure = _graph_violin(prepared, alpha=alpha)
    elif prepared.graph_type == "scatter":
        figure = _graph_scatter(
            prepared, alpha=alpha, linear_regression=prepared.linear_regression
        )
    elif prepared.graph_type == "line":
        figure = _graph_line(prepared)
    elif prepared.graph_type == "area":
        figure = _graph_area(prepared, alpha=alpha)
    elif prepared.graph_type == "timeline":
        figure = _graph_timeline(prepared, alpha=alpha)
    else:
        raise GraphRenderingError(
            f"Graph '{prepared.graph_type}' cannot be rendered by Kraken"
        )

    explicit_width = width
    explicit_height = height
    if figsize is not None:
        if explicit_width is None:
            explicit_width = max(300, figsize[0] * 100)
        if explicit_height is None:
            explicit_height = max(250, figsize[1] * 100)
    if scroll and explicit_width is None:
        explicit_width = 2200
    if (
        prepared.graph_type == "timeline"
        and explicit_height is None
        and prepared.y is not None
    ):
        timeline_rows = int(prepared.plot_data[prepared.y].nunique(dropna=True))
        explicit_height = min(1_000, max(450, 180 + timeline_rows * 18))

    legend_column = prepared.group_colour or prepared.colour_on
    default_y_title = (
        "Density"
        if prepared.graph_type == "density" and prepared.y is None
        else graph_label(prepared.y)
        if prepared.y
        else None
    )
    apply_kraken_theme(
        figure,
        graph_type=prepared.graph_type,
        title=title,
        x_title=x_label or graph_label(prepared.x),
        y_title=y_label or default_y_title,
        legend_title=(
            graph_label(legend_column) if legend_column is not None else None
        ),
        width=explicit_width,
        height=explicit_height,
    )
    if alpha is not None:
        if prepared.graph_type == "scatter":
            for trace in figure.data:
                is_regression = (
                    trace.type in {"scatter", "scattergl"}
                    and trace.mode == "lines"
                    and str(trace.name).startswith("Linear regression")
                )
                if is_regression:
                    trace.opacity = 1
                elif trace.type in {"scatter", "scattergl"}:
                    trace.opacity = None
                    trace.marker.opacity = alpha
                else:
                    trace.opacity = alpha
        else:
            figure.update_traces(opacity=alpha)
    return figure


def render_graph(
    prepared: PreparedGraph,
    *,
    title: str,
    x_label: str | None,
    y_label: str | None,
    figsize: tuple[int, int] | None,
    width: int | None,
    height: int | None,
    scroll: bool,
    bw_adjust: float,
    alpha: float | None,
    showfliers: bool,
) -> go.Figure:
    """Render validated data and categorise anticipated Plotly input failures."""
    try:
        return _render_prepared_graph(
            prepared,
            title=title,
            x_label=x_label,
            y_label=y_label,
            figsize=figsize,
            width=width,
            height=height,
            scroll=scroll,
            bw_adjust=bw_adjust,
            alpha=alpha,
            showfliers=showfliers,
        )
    except GraphingError:
        raise
    except (TypeError, ValueError) as exc:
        raise GraphRenderingError(
            f"Graph '{prepared.graph_type}' could not render prepared x column "
            f"'{prepared.x}' and y column {prepared.y!r}. Verify the accepted "
            "column roles and Plotly-compatible renderer options."
        ) from exc
