"""Shared visual styling for Kraken's Plotly graph renderers."""

import plotly.graph_objects as go  # type: ignore[import-untyped]

from kraken.graphing.models import GraphType

KRAKEN_COLOUR_SEQUENCE = (
    "#005EB8",  # blue
    "#E87722",  # orange
    "#00A499",  # teal
    "#AE2573",  # magenta
    "#7C3AED",  # violet
    "#007F3B",  # green
    "#4C6272",  # slate
    "#FFB81C",  # gold
    "#661100",  # deep brown
    "#FB00D1",  # fuchsia
    "#90AD1C",  # lime
    "#00B5F7",  # sky blue
    "#FB0D0D",  # red
    "#85660D",  # ochre
    "#A777F1",  # lavender
    "#E45756",  # coral
    "#1CA71C",  # bright green
    "#750D86",  # plum
    "#6F4070",  # mauve
    "#D9AF6B",  # tan
    "#8C564B",  # brown
    "#DA16FF",  # electric purple
    "#9C9C5E",  # muted olive
    "#E48F72",  # salmon
)
KRAKEN_MISSING_COLOUR = "#8A8D8F"
KRAKEN_TEXT_COLOUR = "#263238"
KRAKEN_MUTED_TEXT_COLOUR = "#52606D"
KRAKEN_GRID_COLOUR = "#E8EDF2"
KRAKEN_AXIS_COLOUR = "#C5CED6"
KRAKEN_FONT_FAMILY = "Arial, Helvetica, sans-serif"

KRAKEN_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        colorway=list(KRAKEN_COLOUR_SEQUENCE),
        font={
            "family": KRAKEN_FONT_FAMILY,
            "size": 13,
            "color": KRAKEN_TEXT_COLOUR,
        },
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        hoverlabel={
            "bgcolor": "#FFFFFF",
            "bordercolor": KRAKEN_AXIS_COLOUR,
            "font": {
                "family": KRAKEN_FONT_FAMILY,
                "size": 12,
                "color": KRAKEN_TEXT_COLOUR,
            },
            "align": "left",
        },
        xaxis={
            "showgrid": False,
            "showline": True,
            "linecolor": KRAKEN_AXIS_COLOUR,
            "linewidth": 1,
            "ticks": "outside",
            "tickcolor": KRAKEN_AXIS_COLOUR,
            "ticklen": 4,
            "zeroline": False,
            "automargin": True,
            "title": {"standoff": 12},
        },
        yaxis={
            "showgrid": True,
            "gridcolor": KRAKEN_GRID_COLOUR,
            "gridwidth": 1,
            "showline": True,
            "linecolor": KRAKEN_AXIS_COLOUR,
            "linewidth": 1,
            "ticks": "outside",
            "tickcolor": KRAKEN_AXIS_COLOUR,
            "ticklen": 4,
            "zeroline": True,
            "zerolinecolor": KRAKEN_AXIS_COLOUR,
            "zerolinewidth": 1,
            "automargin": True,
            "title": {"standoff": 12},
        },
        legend={
            "bgcolor": "rgba(255,255,255,0.88)",
            "borderwidth": 0,
            "font": {"size": 12, "color": KRAKEN_TEXT_COLOUR},
            "title": {"font": {"size": 12, "color": KRAKEN_MUTED_TEXT_COLOUR}},
            "tracegroupgap": 5,
            "groupclick": "togglegroup",
            "itemclick": "toggle",
            "itemdoubleclick": "toggleothers",
        },
    )
)

_AGGREGATE_LABELS = {
    "count": "Count",
    "countd": "Distinct Count",
    "sum": "Sum",
    "mean": "Mean",
    "mode": "Mode",
    "median": "Median",
}
_LABEL_ACRONYMS = {"api", "ci", "crp", "id", "imd", "kde", "nhs", "sql", "wbc"}


def _title_case_name(name: str) -> str:
    return " ".join(
        word.upper() if word.lower() in _LABEL_ACRONYMS else word.title()
        for word in name.split("_")
    )


def graph_label(name: str) -> str:
    """Turn Kraken's internal graph columns into concise display labels."""
    aggregate, separator, source = name.partition("_of_")
    if separator and aggregate in _AGGREGATE_LABELS:
        source = source.removesuffix("_y")
        return f"{_AGGREGATE_LABELS[aggregate]} {_title_case_name(source)}"
    return _title_case_name(name)


def colour_with_alpha(colour: str, alpha: float) -> str:
    """Convert a hexadecimal colour to an rgba colour."""
    if not colour.startswith("#") or len(colour) != 7:
        return colour
    red, green, blue = (int(colour[index : index + 2], 16) for index in (1, 3, 5))
    return f"rgba({red},{green},{blue},{alpha})"


def darken_colour(colour: str, factor: float = 0.72) -> str:
    """Darken a hexadecimal trace colour while preserving its hue."""
    if not colour.startswith("#") or len(colour) != 7:
        return colour
    channels = [
        max(0, min(255, round(int(colour[index : index + 2], 16) * factor)))
        for index in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _style_facet_annotations(figure: go.Figure) -> None:
    for annotation in figure.layout.annotations or ():
        if isinstance(annotation.text, str) and "=" in annotation.text:
            annotation.text = annotation.text.split("=", 1)[1]
        annotation.update(
            font={"size": 12, "color": KRAKEN_MUTED_TEXT_COLOUR},
        )


def _style_renderer_traces(figure: go.Figure, graph_type: GraphType) -> None:
    if graph_type in {"bar", "stacked", "histogram", "timeline"}:
        figure.update_traces(
            marker_line_color="#FFFFFF",
            marker_line_width=0.6,
            selector={"type": "bar"},
        )

    if graph_type == "line":
        figure.update_traces(
            line_width=2.4,
            marker_size=6,
            marker_line_color="#FFFFFF",
            marker_line_width=0.75,
            selector={"type": "scatter"},
        )
    elif graph_type == "area":
        figure.update_traces(line_width=1.8, selector={"type": "scatter"})
    elif graph_type == "scatter":
        figure.update_traces(
            marker_size=7,
            marker_line_color="#FFFFFF",
            marker_line_width=0.6,
            selector={"type": "scatter"},
        )
    elif graph_type == "box":
        figure.update_traces(
            opacity=0.86,
            line_width=1.5,
            marker_size=5,
            selector={"type": "box"},
        )
    elif graph_type == "violin":
        figure.update_traces(
            opacity=0.72,
            line_width=1.4,
            box_visible=True,
            meanline_visible=True,
            scalemode="width",
            selector={"type": "violin"},
        )

    if graph_type in {"bar", "line"}:
        for trace in figure.data:
            error_y = getattr(trace, "error_y", None)
            if error_y is None or (
                getattr(error_y, "array", None) is None
                and getattr(error_y, "arrayminus", None) is None
            ):
                continue
            marker_colour = getattr(getattr(trace, "marker", None), "color", None)
            line_colour = getattr(getattr(trace, "line", None), "color", None)
            trace_colour = str(marker_colour or line_colour or KRAKEN_TEXT_COLOUR)
            error_colour = (
                darken_colour(trace_colour, factor=0.62)
                if trace_colour.startswith("#")
                else KRAKEN_TEXT_COLOUR
            )
            error_y.update(color=error_colour, thickness=1.5, width=4)


def _style_missing_group(figure: go.Figure) -> None:
    for trace in figure.data:
        if str(trace.name) != "(Missing)":
            continue
        if getattr(trace, "marker", None) is not None:
            trace.marker.color = KRAKEN_MISSING_COLOUR
        if getattr(trace, "line", None) is not None:
            trace.line.color = KRAKEN_MISSING_COLOUR
        if getattr(trace, "fill", None):
            trace.fillcolor = colour_with_alpha(KRAKEN_MISSING_COLOUR, 0.35)


def apply_kraken_theme(
    figure: go.Figure,
    *,
    graph_type: GraphType,
    title: str,
    x_title: str,
    y_title: str | None,
    legend_title: str | None,
    width: float | None,
    height: float | None,
) -> None:
    """Apply shared layout and renderer-specific polish to a Plotly figure."""
    hovermode = "x unified" if graph_type in {"line", "area"} else "closest"
    layout_options: dict[str, object] = {
        "template": KRAKEN_TEMPLATE,
        "title": {
            "text": title,
            "font": {"size": 20, "color": KRAKEN_TEXT_COLOUR},
            "x": 0.02,
            "xanchor": "left",
            "y": 0.97,
            "yanchor": "top",
        },
        "xaxis_title": x_title,
        "yaxis_title": y_title,
        "legend_title_text": legend_title,
        "autosize": width is None,
        "width": width,
        "height": height,
        "hovermode": hovermode,
        "margin": {"l": 72, "r": 32, "t": 82, "b": 68, "pad": 2},
    }
    if graph_type == "histogram":
        layout_options.update(bargap=0, bargroupgap=0, barcornerradius=0)
    elif graph_type in {"bar", "stacked"}:
        layout_options.update(bargap=0.18, bargroupgap=0.06, barcornerradius=3)
    elif graph_type == "timeline":
        layout_options.update(bargap=0.12, barcornerradius=3)

    figure.update_layout(**layout_options)
    figure.update_xaxes(
        showgrid=graph_type == "timeline",
        gridcolor=KRAKEN_GRID_COLOUR,
        automargin=True,
    )
    figure.update_yaxes(
        showgrid=graph_type != "timeline",
        gridcolor=KRAKEN_GRID_COLOUR,
        automargin=True,
    )
    if graph_type == "timeline":
        figure.update_yaxes(autorange="reversed")

    _style_missing_group(figure)
    _style_renderer_traces(figure, graph_type)
    _style_facet_annotations(figure)
