import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from kraken.classes.pack_lists import ResultList
from kraken.classes.packs import Result
from kraken.exceptions import (
    GraphAggregationError,
    GraphCapabilityError,
    GraphColumnError,
    GraphConversionError,
    GraphDataError,
    GraphDataTypeError,
    GraphExportDependencyError,
    GraphExportError,
    GraphingError,
    GraphRenderingError,
    InsufficientGraphDataError,
    TimelineDataError,
)
from kraken.graphing.graphing import graph
from kraken.graphing.graphing_support import prepare_graph
from kraken.graphing.graphing_support_lists import graph_list
from kraken.graphing.graphing_theme import (
    KRAKEN_COLOUR_SEQUENCE,
    KRAKEN_MISSING_COLOUR,
    darken_colour,
    graph_label,
)
from kraken.graphing.models import GraphResult, GraphType
from kraken.support.readout import readout

# Data preparation


def test_prepare_graph_defaults_to_counts_without_mutating_input() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"], "unused": [1, 2, 3]})
    original = source.copy(deep=True)

    prepared = prepare_graph(source, x="category", graph_type="bar")

    expected = pd.DataFrame({"category": ["a", "b"], "count_of_category": [2, 1]})
    pd.testing.assert_frame_equal(prepared.data, expected)
    pd.testing.assert_frame_equal(source, original)
    assert prepared.y == "count_of_category"


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [
        ("count", [2, 1]),
        ("countd", [2, 1]),
        ("sum", [6, 5]),
        ("mean", [3.0, 5.0]),
        ("mode", [2, 5]),
        ("median", [3.0, 5.0]),
    ],
)
def test_prepare_graph_supports_y_aggregations(
    aggregation: str, expected: list[float]
) -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"], "value": [2, 4, 5]})

    prepared = prepare_graph(
        source,
        x="category",
        y="value",
        graph_type="bar",
        y_agg=aggregation,
    )

    assert prepared.y == f"{aggregation}_of_value"
    assert prepared.data[prepared.y].tolist() == expected


def test_prepare_graph_groups_aggregates_by_colour() -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "a", "b"],
            "segment": ["one", "one", "two", "one"],
        }
    )

    prepared = prepare_graph(
        source, x="category", graph_type="bar", group_colour="segment"
    )

    assert prepared.group_colour == "segment"
    assert prepared.data.to_dict("records") == [
        {"category": "a", "segment": "one", "count_of_category": 2},
        {"category": "a", "segment": "two", "count_of_category": 1},
        {"category": "b", "segment": "one", "count_of_category": 1},
    ]


def test_prepare_graph_aggregates_dates() -> None:
    source = pd.DataFrame(
        {"event_date": pd.to_datetime(["2025-01-01", "2025-05-01", "2026-01-01"])}
    )

    prepared = prepare_graph(
        source,
        x="event_date",
        graph_type="line",
        x_agg="year",
        convert_dates=False,
    )

    assert prepared.data["event_date"].tolist() == [
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2026-01-01"),
    ]
    assert prepared.data["count_of_event_date"].tolist() == [2, 1]


def test_prepare_graph_aggregates_monday_to_sunday_weeks() -> None:
    source = pd.DataFrame(
        {
            "event_date": pd.to_datetime(
                ["2025-08-17", "2025-08-18", "2025-08-24", "2025-08-25"]
            )
        }
    )

    prepared = prepare_graph(
        source,
        x="event_date",
        graph_type="line",
        x_agg="week",
        convert_dates=False,
    )

    assert prepared.data["event_date"].tolist() == [
        pd.Timestamp("2025-08-11"),
        pd.Timestamp("2025-08-18"),
        pd.Timestamp("2025-08-25"),
    ]
    assert prepared.data["count_of_event_date"].tolist() == [1, 2, 1]


def test_prepare_graph_aggregates_numeric_bins() -> None:
    source = pd.DataFrame({"age": [1, 9, 11]})

    prepared = prepare_graph(source, x="age", graph_type="bar", x_agg=10)

    assert prepared.data["age"].astype(str).tolist() == ["[0, 10)", "[10, 20)"]
    assert prepared.data["count_of_age"].tolist() == [2, 1]


def test_prepare_graph_aggregates_negative_numeric_bins() -> None:
    source = pd.DataFrame({"temperature": [-11, -1, 1]})

    prepared = prepare_graph(source, x="temperature", graph_type="bar", x_agg=10)

    assert prepared.data["temperature"].astype(str).tolist() == [
        "[-20, -10)",
        "[-10, 0)",
        "[0, 10)",
    ]
    assert prepared.data["count_of_temperature"].tolist() == [1, 1, 1]


@pytest.mark.parametrize("graph_type", ["bar", "line", "area"])
def test_graph_orders_numeric_bins_from_negative_to_positive(
    graph_type: str,
) -> None:
    source = pd.DataFrame(
        {
            "value": [15, -15, 8, -1, 1],
            "amount": [1, 2, 3, 4, 5],
        }
    )

    result = graph(
        source,
        x="value",
        y="amount",
        x_agg=7,
        y_agg="sum",
        graph=graph_type,
        show=False,
    )

    expected_order = [
        "[-21, -14)",
        "[-14, -7)",
        "[-7, 0)",
        "[0, 7)",
        "[7, 14)",
        "[14, 21)",
    ]
    assert result.figure is not None
    assert list(result.figure.layout.xaxis.categoryarray) == expected_order
    assert list(result.figure.data[0].x) == expected_order


def test_graph_retains_empty_numeric_bin_categories() -> None:
    source = pd.DataFrame(
        {
            "value": [-15, -1, 1, 8, 15],
            "amount": [1, 2, 3, 4, 5],
            "group": ["a", "a", "a", "a", "a"],
        }
    )

    result = graph(
        source,
        x="value",
        y="amount",
        x_agg=7,
        y_agg="sum",
        graph="bar",
        group_colour="group",
        show=False,
    )

    assert result.figure is not None
    assert list(result.figure.layout.xaxis.categoryarray) == [
        "[-21, -14)",
        "[-14, -7)",
        "[-7, 0)",
        "[0, 7)",
        "[7, 14)",
        "[14, 21)",
    ]
    assert "[-14, -7)" not in result.figure.data[0].x


@pytest.mark.parametrize("width", [0, -1])
def test_prepare_graph_rejects_non_positive_numeric_bin_width(width: int) -> None:
    source = pd.DataFrame({"value": [1, 2]})

    with pytest.raises(GraphAggregationError, match="finite positive"):
        prepare_graph(source, x="value", graph_type="bar", x_agg=width)


def test_prepare_graph_keeps_row_level_data_for_scatter() -> None:
    source = pd.DataFrame({"x": [1, 2], "y": [3, 4], "group": ["a", "b"]})

    prepared = prepare_graph(
        source, x="x", y="y", graph_type="scatter", group_colour="group"
    )

    pd.testing.assert_frame_equal(prepared.data, source)
    assert prepared.y == "y"


def test_prepare_graph_handles_duplicate_x_y_and_colour() -> None:
    source = pd.DataFrame({"value": [1, 1, 2]})

    prepared = prepare_graph(
        source,
        x="value",
        y="value",
        graph_type="bar",
        group_colour="value",
    )

    assert prepared.group_colour is None
    assert prepared.colour_on == "value"
    assert prepared.y == "count_of_value_y"
    assert prepared.data[prepared.y].tolist() == [2, 1]


def test_prepare_graph_preserves_result_categories_but_converts_plot_data() -> None:
    source = pd.DataFrame({"age": [1, 11]})

    prepared = prepare_graph(
        source,
        x="age",
        graph_type="bar",
        x_agg=10,
        convert_categories_to_str=True,
    )

    assert str(prepared.data["age"].dtype) == "category"
    assert str(prepared.plot_data["age"].dtype) == "object"


def test_prepare_graph_rejects_unknown_graph_and_columns() -> None:
    source = pd.DataFrame({"value": [1]})

    with pytest.raises(GraphCapabilityError, match="Graph 'unknown' not supported"):
        prepare_graph(source, x="value", graph_type="unknown")

    with pytest.raises(GraphColumnError, match="column 'missing'.*not found"):
        prepare_graph(source, x="missing", graph_type="bar")


# Public results and core renderers


def test_graph_returns_interactive_bar_and_prepared_data() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"]})

    result = graph(source, x="category", graph="bar", show=False)

    assert isinstance(result, GraphResult)
    assert isinstance(result.figure, go.Figure)
    assert [trace.type for trace in result.figure.data] == ["bar"]
    assert result.data["count_of_category"].tolist() == [2, 1]
    assert result.figure.layout.xaxis.title.text == "Category"


def test_graph_result_repr_is_compact_and_contains_key_details() -> None:
    source = pd.DataFrame({"category": ["a", "b"], "value": [1, 2]})

    result = graph(source, x="category", y="value", graph="bar", show=False)
    representation = repr(result)

    assert representation.startswith("GraphResult(")
    assert "graph_type='bar'" in representation
    assert "shape=(2, 2)" in representation
    assert "x='category'" in representation
    assert "y='count_of_value'" in representation
    assert "Plotly" not in representation


def test_graph_result_repr_handles_aggregation_only_results() -> None:
    result = graph(
        pd.DataFrame({"category": ["a", "b"]}),
        x="category",
        show=False,
    )

    representation = repr(result)

    assert "graph_type='aggregation'" in representation
    assert "figure=None" in representation
    assert "x='category'" in representation


def test_graph_handles_numpy_string_categories_with_y_aggregation() -> None:
    source = pd.DataFrame(
        {
            "specialty": np.array(
                ["Cardiology", "Respiratory", "Cardiology", "Respiratory"],
                dtype=np.str_,
            ),
            "length_of_stay_days": [2, 4, 6, 8],
        }
    )

    result = graph(
        source,
        x="specialty",
        y="length_of_stay_days",
        y_agg="mean",
        graph="bar",
        alpha=0.8,
        show=False,
    )

    assert result.figure is not None
    assert result.data["specialty"].tolist() == ["Cardiology", "Respiratory"]
    assert result.data["mean_of_length_of_stay_days"].tolist() == [4.0, 6.0]
    assert len(result.figure.data) == 1
    assert all(trace.opacity == 0.8 for trace in result.figure.data)


def test_histogram_counts_distinct_numeric_values_without_automatic_bins() -> None:
    source = pd.DataFrame({"value": [0.1, 0.1, 0.2, 1.9]})

    result = graph(source, x="value", graph="histogram", show=False)

    assert result.graph_type == "histogram"
    assert result.x == "value"
    assert result.y == "count_of_value"
    assert result.data[result.x].tolist() == [0.1, 0.2, 1.9]
    assert result.data[result.y].tolist() == [2, 1, 1]
    assert result.figure is not None
    assert [trace.type for trace in result.figure.data] == ["bar"]


def test_histogram_uses_numeric_x_aggregation_bins() -> None:
    source = pd.DataFrame({"value": [0.2, 0.8, 1.1, 2.4]})

    result = graph(source, x="value", x_agg=1, graph="histogram", show=False)

    assert result.y == "count_of_value"
    assert result.data[result.y].tolist() == [2, 1, 1]
    assert result.data[result.x].tolist() == [0.5, 1.5, 2.5]


def test_graph_builds_timeline_from_start_and_end_dates() -> None:
    source = pd.DataFrame(
        {
            "start": ["2025-01-01", "2025-01-03"],
            "end": ["2025-01-02", "2025-01-05"],
            "episode": ["one", "two"],
        }
    )

    result = graph(
        source,
        x="start",
        x_end="end",
        y="episode",
        graph="timeline",
        show=False,
    )

    assert result.graph_type == "timeline"
    assert result.x_end == "end"
    assert result.figure is not None
    assert [trace.type for trace in result.figure.data] == ["bar"]


def test_timeline_requires_end_column() -> None:
    source = pd.DataFrame({"start": ["2025-01-01"], "episode": ["one"]})

    with pytest.raises(GraphColumnError, match="requires an x_end column"):
        graph(source, x="start", y="episode", graph="timeline", show=False)


# Capability validation and graph modifiers


@pytest.mark.parametrize(
    ("graph_type", "arguments"),
    [
        ("box", {"x": "category"}),
        ("violin", {"x": "category"}),
        ("scatter", {"x": "x"}),
        ("timeline", {"x": "start", "x_end": "end"}),
    ],
)
def test_graph_types_with_mandatory_y_reject_missing_y(
    graph_type: str, arguments: dict[str, object]
) -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "b"],
            "x": [1.0, 2.0],
            "start": pd.date_range("2025-01-01", periods=2),
            "end": pd.date_range("2025-01-02", periods=2),
        }
    )

    with pytest.raises(ValueError, match="y-values are mandatory"):
        graph(source, graph=graph_type, show=False, **arguments)


@pytest.mark.parametrize(
    ("graph_type", "arguments"),
    [
        ("density", {"x": "label"}),
        ("histogram", {"x": "label"}),
        ("scatter", {"x": "label", "y": "value"}),
    ],
)
def test_numeric_x_graph_types_reject_non_numeric_x(
    graph_type: str, arguments: dict[str, object]
) -> None:
    source = pd.DataFrame({"label": ["one", "two", "three"], "value": [1.0, 2.0, 3.0]})

    with pytest.raises(GraphConversionError, match="supported quantitative dtype"):
        graph(source, graph=graph_type, show=False, **arguments)


def test_graph_supports_facets_and_hover_columns() -> None:
    source = pd.DataFrame(
        {
            "x": [1, 2, 3, 4],
            "y": [4, 3, 2, 1],
            "sex": ["F", "F", "M", "M"],
            "patient_id": ["P1", "P2", "P3", "P4"],
        }
    )

    result = graph(
        source,
        x="x",
        y="y",
        graph="scatter",
        facet_col="sex",
        hover_columns=["patient_id"],
        linear_regression=False,
        show=False,
    )

    assert result.figure is not None
    assert result.facet_col == "sex"
    assert result.hover_columns == ("patient_id",)
    assert result.figure.layout.grid is not None
    assert result.figure.data[0].customdata is not None


@pytest.mark.parametrize(
    ("facet_arguments", "expected_traces"),
    [
        ({"facet_row": "row"}, 2),
        ({"facet_col": "column"}, 2),
        ({"facet_row": "row", "facet_col": "column"}, 4),
    ],
)
def test_graph_supports_facet_rows_columns_and_grids(
    facet_arguments: dict[str, str], expected_traces: int
) -> None:
    source = pd.DataFrame.from_records(
        {
            "x": float(x),
            "y": float(x + row_index + column_index),
            "row": row,
            "column": column,
        }
        for row_index, row in enumerate(("top", "bottom"))
        for column_index, column in enumerate(("left", "right"))
        for x in (1, 2)
    )

    result = graph(
        source,
        x="x",
        y="y",
        graph="scatter",
        linear_regression=False,
        show=False,
        **facet_arguments,
    )

    assert result.figure is not None
    assert len(result.figure.data) == expected_traces


def test_graph_supports_scatter_marginal_plots() -> None:
    source = pd.DataFrame({"x": [1, 2, 3, 4], "y": [4, 3, 2, 1]})

    result = graph(
        source,
        x="x",
        y="y",
        graph="scatter",
        marginal_x="histogram",
        marginal_y="box",
        linear_regression=False,
        show=False,
    )

    assert result.figure is not None
    assert len(result.figure.data) == 3


@pytest.mark.parametrize(
    ("graph_type", "expected"),
    [
        ("aggregation", (False, False, "none", "data", False)),
        ("density", (False, False, "none", "none", False)),
        ("histogram", (True, False, "group", "none", False)),
        ("bar", (True, False, "group", "figure", False)),
        ("box", (True, False, "row", "none", False)),
        ("violin", (True, False, "row", "none", False)),
        ("scatter", (True, True, "row", "none", True)),
        ("stacked", (True, False, "group", "none", False)),
        ("line", (True, False, "group", "figure", False)),
        ("area", (False, False, "none", "none", False)),
        ("timeline", (True, False, "row", "none", False)),
    ],
)
def test_graph_settings_define_modifier_capabilities(
    graph_type: GraphType, expected: tuple[bool, bool, str, str, bool]
) -> None:
    settings = graph_list[graph_type]

    assert (
        settings.facets,
        settings.marginals,
        settings.hover,
        settings.confidence_intervals,
        settings.regression,
    ) == expected


@pytest.mark.parametrize(
    ("graph_type", "arguments", "message"),
    [
        ("density", {"facet_col": "group"}, "does not support facets"),
        ("area", {"facet_col": "group"}, "does not support facets"),
        ("aggregation", {"facet_col": "group"}, "does not support facets"),
        ("bar", {"marginal_x": "histogram"}, "does not support marginal"),
        ("density", {"hover_columns": ["detail"]}, "does not support hover"),
        ("area", {"hover_columns": ["detail"]}, "does not support hover"),
        ("aggregation", {"hover_columns": ["detail"]}, "does not support hover"),
        ("bar", {"hover_columns": ["detail"]}, "aggregates rows"),
        (
            "stacked",
            {
                "y": "value",
                "y_agg": "mean",
                "error": "confidence_interval",
            },
            "does not support confidence intervals",
        ),
        ("scatter", {"x_agg": 1}, "does not support x_agg"),
        ("scatter", {"y_agg": "mean"}, "does not support y_agg"),
        ("histogram", {"y": "value"}, "does not support a y column"),
        ("bar", {"x_end": "end"}, "does not support x_end"),
    ],
)
def test_prepare_graph_rejects_unsupported_capability_combinations(
    graph_type: str, arguments: dict[str, object], message: str
) -> None:
    source = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0],
            "value": [2.0, 4.0, 6.0],
            "group": ["a", "a", "b"],
            "detail": ["one", "two", "three"],
            "end": [2.0, 3.0, 4.0],
        }
    )

    with pytest.raises(ValueError, match=message):
        prepare_graph(source, x="x", graph_type=graph_type, **arguments)


def test_aggregated_graph_retains_supported_facet_and_hover_metadata() -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "b", "b"],
            "value": [1, 2, 3, 4],
            "group": ["one", "two", "one", "two"],
        }
    )

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="sum",
        graph="bar",
        facet_col="group",
        hover_columns=["group", "group"],
        show=False,
    )

    assert result.facet_col == "group"
    assert result.hover_columns == ("group",)
    assert "group" in result.data.columns
    assert result.figure is not None
    assert len(result.figure.layout.annotations) == 2
    assert all(trace.customdata is not None for trace in result.figure.data)
    assert all(
        "Group=%{customdata[0]}" in trace.hovertemplate for trace in result.figure.data
    )


@pytest.mark.parametrize(
    ("graph_type", "arguments"),
    [
        ("scatter", {"x": "x", "y": "value", "y_agg": "mean"}),
        (
            "timeline",
            {
                "x": "start",
                "x_end": "end",
                "y": "episode",
                "y_agg": "mean",
            },
        ),
        ("stacked", {"x": "category", "y": "value", "y_agg": "mean"}),
        ("area", {"x": "category", "y": "value", "y_agg": "mean"}),
        ("histogram", {"x": "x", "y": "value", "y_agg": "mean"}),
        ("box", {"x": "category", "y": "value", "y_agg": "mean"}),
        ("violin", {"x": "category", "y": "value", "y_agg": "mean"}),
        ("density", {"x": "x", "y": "value", "y_agg": "mean"}),
    ],
)
def test_graph_rejects_confidence_intervals_for_unsupported_renderers(
    graph_type: GraphType, arguments: dict[str, object]
) -> None:
    source = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0],
            "category": ["a", "a", "b"],
            "value": [2.0, 4.0, 6.0],
            "start": pd.date_range("2025-01-01", periods=3),
            "end": pd.date_range("2025-01-02", periods=3),
            "episode": ["one", "two", "three"],
        }
    )

    with pytest.raises(ValueError, match="does not support confidence intervals"):
        graph(
            source,
            graph=graph_type,
            error="confidence_interval",
            show=False,
            **arguments,
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"facet_row": "category"},
        {"facet_col": "value"},
        {"facet_row": "facet", "facet_col": "facet"},
    ],
)
def test_graph_rejects_facets_that_duplicate_axis_or_facet_roles(
    arguments: dict[str, str],
) -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "b", "b"],
            "value": [1.0, 2.0, 3.0, 4.0],
            "facet": ["one", "two", "one", "two"],
        }
    )

    with pytest.raises(ValueError, match="reuse axis|different columns"):
        graph(
            source,
            x="category",
            y="value",
            y_agg="mean",
            graph="bar",
            show=False,
            **arguments,
        )


# Confidence intervals


@pytest.mark.parametrize("graph_type", ["bar", "line"])
def test_figure_confidence_interval_capability_matches_result_metadata(
    graph_type: str,
) -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "a", "b", "b", "b"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="mean",
        error="ci",
        graph=graph_type,
        show=False,
    )

    assert result.error == "confidence_interval"
    assert result.error_plus in result.data.columns
    assert result.error_minus in result.data.columns
    assert result.figure is not None
    error_y = result.figure.data[0].error_y
    assert error_y is not None
    assert error_y.color not in {None, "#FFFFFF", "white"}
    assert error_y.thickness == 1.5
    assert error_y.width == 4


def test_aggregation_confidence_interval_capability_is_data_only() -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "a", "b", "b", "b"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="mean",
        error="confidence_interval",
        graph="aggregation",
        show=False,
    )

    assert result.figure is None
    assert result.error == "confidence_interval"
    assert result.error_lower in result.data.columns
    assert result.error_upper in result.data.columns


def test_confidence_intervals_group_by_facets_and_colour() -> None:
    source = pd.DataFrame.from_records(
        {
            "category": category,
            "facet": facet,
            "group": group,
            "value": float(category_index + facet_index + group_index) + repeat,
        }
        for category_index, category in enumerate(("a", "b"))
        for facet_index, facet in enumerate(("one", "two"))
        for group_index, group in enumerate(("low", "high"))
        for repeat in (0.0, 1.0)
    )

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="mean",
        group_colour="group",
        facet_col="facet",
        error="confidence_interval",
        graph="bar",
        show=False,
    )

    assert len(result.data) == 8
    assert result.error_lower is not None
    assert result.error_upper is not None
    assert result.data[result.error_lower].notna().all()
    assert result.data[result.error_upper].notna().all()
    assert result.figure is not None
    assert len(result.figure.data) == 4
    assert all(trace.error_y is not None for trace in result.figure.data)


def test_single_observation_confidence_interval_remains_null() -> None:
    source = pd.DataFrame(
        {
            "category": ["many", "many", "one"],
            "value": [1.0, 3.0, 5.0],
        }
    )

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="mean",
        error="confidence_interval",
        graph="line",
        show=False,
    )

    assert result.error_lower is not None
    assert result.error_upper is not None
    singleton = result.data.loc[result.data["category"] == "one"].iloc[0]
    repeated = result.data.loc[result.data["category"] == "many"].iloc[0]
    assert pd.isna(singleton[result.error_lower])
    assert pd.isna(singleton[result.error_upper])
    assert pd.notna(repeated[result.error_lower])
    assert pd.notna(repeated[result.error_upper])


def test_graph_adds_t_based_confidence_intervals_to_mean_bars() -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "a", "b", "b", "b"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        }
    )

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="mean",
        error="confidence_interval",
        graph="bar",
        show=False,
    )

    assert result.figure is not None
    assert result.error == "confidence_interval"
    assert result.error_lower in result.data.columns
    assert result.error_upper in result.data.columns
    assert result.error_plus in result.data.columns
    assert result.error_minus in result.data.columns
    assert result.data[result.error_lower].notna().all()
    assert result.data[result.error_upper].notna().all()
    assert result.figure.data[0].error_y is not None


@pytest.mark.parametrize("graph_type", ["aggregation", "bar", "line"])
def test_graph_adds_confidence_intervals_after_numeric_x_aggregation(
    graph_type: str,
) -> None:
    source = pd.DataFrame(
        {
            "age": [0.2, 0.8, 1.1, 1.9],
            "value": [1.0, 3.0, 5.0, 7.0],
        }
    )

    result = graph(
        source,
        x="age",
        x_agg=1,
        y="value",
        y_agg="mean",
        error="confidence_interval",
        graph=graph_type,  # type: ignore[arg-type]
        show=False,
    )

    assert result.error_plus is not None
    assert list(map(str, result.data["age"])) == ["[0, 1)", "[1, 2)"]
    assert result.data["count"].tolist() == [2, 2]
    assert result.data[result.error_plus].notna().all()


def test_graph_adds_confidence_intervals_after_date_aggregation() -> None:
    source = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-01-01", "2025-01-15", "2025-02-01", "2025-02-15"]
            ),
            "value": [1.0, 3.0, 5.0, 7.0],
        }
    )

    result = graph(
        source,
        x="date",
        x_agg="month",
        y="value",
        y_agg="mean",
        error="confidence_interval",
        graph="line",
        show=False,
    )

    assert result.data["date"].tolist() == [
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-02-01"),
    ]
    assert result.error_lower is not None
    assert result.error_upper is not None
    assert result.data[result.error_lower].notna().all()
    assert result.data[result.error_upper].notna().all()
    assert result.figure is not None
    assert result.figure.data[0].error_y is not None


@pytest.mark.parametrize(
    "confidence_level",
    [0, 1, -0.1, 1.1, None, "0.95", True, np.nan, np.inf, -np.inf],
)
def test_graph_rejects_invalid_confidence_level(confidence_level: object) -> None:
    source = pd.DataFrame({"category": ["a", "a"], "value": [1.0, 2.0]})

    with pytest.raises(
        GraphCapabilityError,
        match="confidence_level.*finite real numbers strictly between 0 and 1",
    ):
        graph(
            source,
            x="category",
            y="value",
            y_agg="mean",
            error="confidence_interval",
            confidence_level=confidence_level,  # type: ignore[arg-type]
            graph="bar",
            show=False,
        )


# Common parameter validation


def test_graph_is_responsive_by_default() -> None:
    source = pd.DataFrame({"category": ["a", "b"]})

    result = graph(source, x="category", graph="bar", show=False)

    assert result.figure is not None
    assert result.figure.layout.autosize is True
    assert result.figure.layout.width is None


def test_graph_accepts_explicit_dimensions_and_scroll_canvas() -> None:
    source = pd.DataFrame({"category": ["a", "b"]})

    fixed = graph(source, x="category", graph="bar", width=900, height=500, show=False)
    scrolling = graph(source, x="category", graph="bar", scroll=True, show=False)

    assert fixed.figure is not None
    assert fixed.figure.layout.width == 900
    assert fixed.figure.layout.height == 500
    assert fixed.figure.layout.autosize is False
    assert scrolling.figure is not None
    assert scrolling.figure.layout.width == 2200
    assert scrolling.figure.layout.autosize is False


@pytest.mark.parametrize("bw_adjust", [0, -1, np.nan, np.inf, -np.inf, True, "wide"])
def test_graph_rejects_invalid_density_bandwidth(bw_adjust: object) -> None:
    source = pd.DataFrame({"value": [1.0, 2.0, 3.0]})

    with pytest.raises(ValueError, match="bw_adjust"):
        graph(
            source,
            x="value",
            graph="density",
            bw_adjust=bw_adjust,  # type: ignore[arg-type]
            show=False,
        )


@pytest.mark.parametrize("alpha", [-0.1, 1.1, np.nan, np.inf, -np.inf, True, "opaque"])
def test_graph_rejects_invalid_alpha(alpha: object) -> None:
    source = pd.DataFrame({"category": ["a", "b"]})

    with pytest.raises(ValueError, match="alpha"):
        graph(
            source,
            x="category",
            graph="bar",
            alpha=alpha,  # type: ignore[arg-type]
            show=False,
        )


@pytest.mark.parametrize("name", ["width", "height"])
@pytest.mark.parametrize("value", [0, -1, 1, 9, 10.5, True, "900"])
def test_graph_rejects_invalid_explicit_dimensions(name: str, value: object) -> None:
    source = pd.DataFrame({"category": ["a", "b"]})

    with pytest.raises(ValueError, match=f"{name} must be an integer of at least 10"):
        graph(
            source,
            x="category",
            graph="bar",
            show=False,
            **{name: value},
        )


def test_graph_honours_minimum_explicit_dimensions() -> None:
    result = graph(
        pd.DataFrame({"category": ["a", "b"]}),
        x="category",
        graph="bar",
        width=10,
        height=10,
        show=False,
    )

    assert result.figure is not None
    assert result.figure.layout.width == 10
    assert result.figure.layout.height == 10


# Renderer behavior and discrete grouping


def test_graph_builds_grouped_and_stacked_bars() -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "b", "b"],
            "segment": ["one", "two", "one", "two"],
        }
    )

    grouped = graph(
        source,
        x="category",
        graph="bar",
        group_colour="segment",
        show=False,
    )
    stacked = graph(
        source,
        x="category",
        graph="stacked",
        group_colour="segment",
        show=False,
    )

    assert grouped.figure is not None
    assert stacked.figure is not None
    assert len(grouped.figure.data) == 2
    assert grouped.figure.layout.barmode == "group"
    assert len(stacked.figure.data) == 2
    assert stacked.figure.layout.barmode == "stack"


@pytest.mark.parametrize("graph_type", ["bar", "stacked"])
def test_graph_alphabetizes_categorical_bar_x_axis(graph_type: str) -> None:
    source = pd.DataFrame(
        {
            "stage": [
                "3 Project",
                "2 EOI",
                "1 Opportunity",
                "3 Project",
            ],
            "status": ["second", "first", "second", "first"],
        }
    )

    result = graph(
        source,
        x="stage",
        graph=graph_type,
        group_colour="status",
        show=False,
    )

    assert result.figure is not None
    assert list(result.figure.layout.xaxis.categoryarray) == [
        "1 Opportunity",
        "2 EOI",
        "3 Project",
    ]
    assert list(dict.fromkeys(result.data["stage"])) == [
        "3 Project",
        "2 EOI",
        "1 Opportunity",
    ]
    assert [trace.name for trace in result.figure.data] == ["second", "first"]


def test_graph_alphabetizes_bar_x_axis_case_insensitively() -> None:
    result = graph(
        pd.DataFrame({"category": ["beta", "alpha", "Alpha"]}),
        x="category",
        graph="bar",
        show=False,
    )

    assert result.figure is not None
    assert list(result.figure.layout.xaxis.categoryarray) == [
        "Alpha",
        "alpha",
        "beta",
    ]


@pytest.mark.parametrize("ordered", [False, True])
def test_graph_only_preserves_explicitly_ordered_x_categories(ordered: bool) -> None:
    categories = ["New", "In progress", "Closed"]
    source = pd.DataFrame(
        {
            "stage": pd.Categorical(
                ["In progress", "Closed", "New"],
                categories=categories,
                ordered=ordered,
            )
        }
    )

    result = graph(source, x="stage", graph="bar", show=False)

    assert result.figure is not None
    expected = categories if ordered else ["Closed", "In progress", "New"]
    assert list(result.figure.layout.xaxis.categoryarray) == expected


@pytest.mark.parametrize(
    ("graph_type", "arguments"),
    [
        ("bar", {"x": "category"}),
        ("stacked", {"x": "category"}),
        ("histogram", {"x": "x"}),
        ("line", {"x": "x", "y": "y", "y_agg": "sum"}),
        ("area", {"x": "x", "y": "y", "y_agg": "sum"}),
        ("box", {"x": "category", "y": "y"}),
        ("violin", {"x": "category", "y": "y"}),
        ("scatter", {"x": "x", "y": "y", "linear_regression": False}),
        ("density", {"x": "x"}),
        ("timeline", {"x": "start", "x_end": "end", "y": "episode"}),
    ],
)
def test_graph_treats_numeric_colour_groups_as_discrete_traces(
    graph_type: str, arguments: dict[str, object]
) -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "b", "a", "b", "a", "b"],
            "x": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
            "y": [2.0, 4.0, 3.0, 6.0, 5.0, 7.0],
            "group": [1, 1, 1, 2, 2, 2],
            "start": pd.date_range("2025-01-01", periods=6),
            "end": pd.date_range("2025-01-02", periods=6),
            "episode": [f"episode-{number}" for number in range(6)],
        }
    )

    result = graph(
        source,
        graph=graph_type,
        group_colour="group",
        show=False,
        **arguments,
    )

    assert result.figure is not None
    assert [trace.name for trace in result.figure.data] == ["1", "2"]
    assert result.data["group"].dtype == source["group"].dtype


@pytest.mark.parametrize(
    ("groups", "expected_names"),
    [
        ([True, False, True, False], ["True", "False"]),
        (pd.Categorical(["one", "two", "one", "two"]), ["one", "two"]),
    ],
)
def test_graph_treats_boolean_and_categorical_colour_groups_as_discrete(
    groups: object, expected_names: list[str]
) -> None:
    source = pd.DataFrame({"category": ["a", "a", "b", "b"], "group": groups})

    result = graph(
        source,
        x="category",
        graph="bar",
        group_colour="group",
        show=False,
    )

    assert result.figure is not None
    assert [trace.name for trace in result.figure.data] == expected_names
    assert result.data["group"].dtype == source["group"].dtype


def test_graph_preserves_and_labels_missing_colour_groups() -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a", "b", "b"],
            "group": [1.0, np.nan, 1.0, np.nan],
        }
    )

    result = graph(
        source,
        x="category",
        graph="bar",
        group_colour="group",
        show=False,
    )

    assert result.figure is not None
    assert [trace.name for trace in result.figure.data] == ["1.0", "(Missing)"]
    assert result.data["group"].isna().sum() == 2
    assert result.data["group"].dtype == source["group"].dtype


def test_graph_applies_shared_kraken_theme_and_humanized_labels() -> None:
    source = pd.DataFrame(
        {
            "category_name": ["a", "a", "b", "b"],
            "result_value": [1.0, 2.0, 3.0, 4.0],
            "group_name": ["one", "two", "one", None],
        }
    )

    result = graph(
        source,
        x="category_name",
        y="result_value",
        y_agg="mean",
        group_colour="group_name",
        facet_col="group_name",
        hover_columns=["group_name"],
        graph="bar",
        show=False,
    )

    assert result.figure is not None
    figure = result.figure
    assert tuple(figure.layout.template.layout.colorway) == KRAKEN_COLOUR_SEQUENCE
    assert figure.layout.title.x == 0.02
    assert figure.layout.title.xanchor == "left"
    assert figure.layout.xaxis.showgrid is False
    assert figure.layout.yaxis.showgrid is True
    assert figure.layout.bargap == 0.18
    assert figure.layout.barcornerradius == 3
    assert figure.layout.yaxis.title.text == "Mean Result Value"
    assert [annotation.text for annotation in figure.layout.annotations] == [
        "one",
        "two",
        "(Missing)",
    ]
    assert all(trace.marker.line.color == "#FFFFFF" for trace in figure.data)
    missing_trace = next(trace for trace in figure.data if trace.name == "(Missing)")
    assert missing_trace.marker.color == KRAKEN_MISSING_COLOUR
    assert all("Group Name=" in trace.hovertemplate for trace in figure.data)


def test_graph_uses_high_contrast_opening_colours_for_scatter_groups() -> None:
    result = graph(
        pd.DataFrame(
            {
                "x": [1, 2, 1, 2],
                "y": [1, 2, 2, 1],
                "group": ["one", "one", "two", "two"],
            }
        ),
        x="x",
        y="y",
        group_colour="group",
        graph="scatter",
        linear_regression=False,
        show=False,
    )

    assert result.figure is not None
    assert [trace.marker.color for trace in result.figure.data] == [
        "#005EB8",
        "#E87722",
    ]


def test_graph_uses_24_unique_colours_before_cycling() -> None:
    original_colours = (
        "#005EB8",
        "#E87722",
        "#00A499",
        "#AE2573",
        "#7C3AED",
        "#007F3B",
        "#4C6272",
        "#FFB81C",
    )
    assert len(KRAKEN_COLOUR_SEQUENCE) == 24
    assert len(set(KRAKEN_COLOUR_SEQUENCE)) == 24
    assert KRAKEN_COLOUR_SEQUENCE[:8] == original_colours

    result = graph(
        pd.DataFrame(
            {
                "category": ["all"] * 25,
                "group": [f"group-{index:02d}" for index in range(25)],
            }
        ),
        x="category",
        group_colour="group",
        graph="stacked",
        show=False,
    )

    assert result.figure is not None
    plotted_colours = [trace.marker.color for trace in result.figure.data]
    assert plotted_colours[:24] == list(KRAKEN_COLOUR_SEQUENCE)
    assert plotted_colours[24] == KRAKEN_COLOUR_SEQUENCE[0]


def test_graph_label_removes_internal_aggregation_syntax() -> None:
    assert graph_label("mean_of_length_of_stay_days") == "Mean Length Of Stay Days"
    assert graph_label("countd_of_patient_id") == "Distinct Count Patient ID"
    assert graph_label("count_of_value_y") == "Count Value"


def test_stacked_without_group_falls_back_to_bar() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"]})

    result = graph(source, x="category", graph="stacked", show=False)

    assert result.figure is not None
    assert result.figure.layout.barmode == "group"
    assert result.figure.layout.title.text.startswith("Bar Plot:")


def test_graph_builds_box_and_violin_figures() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b", "b"], "value": [1, 2, 3, 10]})

    box = graph(
        source,
        x="category",
        y="value",
        graph="box",
        showfliers=False,
        show=False,
    )
    violin = graph(source, x="category", y="value", graph="violin", show=False)

    assert box.figure is not None
    assert violin.figure is not None
    assert box.figure.data[0].type == "box"
    assert box.figure.data[0].boxpoints is False
    assert box.figure.data[0].opacity == 0.86
    assert box.figure.data[0].line.width == 1.5
    assert violin.figure.data[0].type == "violin"
    assert violin.figure.data[0].box.visible is True
    assert violin.figure.data[0].meanline.visible is True
    assert violin.figure.data[0].opacity == 0.72


def test_graph_scatter_regression_is_opt_in() -> None:
    source = pd.DataFrame({"x": [1, 2, 3], "y": [2, 4, 6]})

    without_regression = graph(source, x="x", y="y", graph="scatter", show=False)
    with_regression = graph(
        source,
        x="x",
        y="y",
        graph="scatter",
        linear_regression=True,
        show=False,
    )

    assert with_regression.figure is not None
    assert without_regression.figure is not None
    assert len(without_regression.figure.data) == 1
    assert [trace.name for trace in with_regression.figure.data] == [
        "",
        "Linear regression",
    ]
    assert with_regression.figure.data[1].showlegend is False


def test_graph_scatter_adds_regression_per_colour_group() -> None:
    source = pd.DataFrame(
        {
            "x": [1, 2, 3, 1, 2, 3],
            "y": [1, 2, 3, 6, 4, 2],
            "group": ["up", "up", "up", "down", "down", "down"],
        }
    )

    result = graph(
        source,
        x="x",
        y="y",
        graph="scatter",
        group_colour="group",
        linear_regression=True,
        show=False,
    )

    assert result.figure is not None
    assert [trace.name for trace in result.figure.data] == [
        "up",
        "down",
        "Linear regression (up)",
        "Linear regression (down)",
    ]
    assert [trace.name for trace in result.figure.data if trace.showlegend] == [
        "up",
        "down",
    ]
    point_traces = {trace.name: trace for trace in result.figure.data[:2]}
    for regression in result.figure.data[2:]:
        group = regression.name.removeprefix("Linear regression (").removesuffix(")")
        point = point_traces[group]
        assert regression.line.color == darken_colour(point.marker.color)
        assert regression.line.dash == "solid"
        assert regression.line.width == 3
        assert regression.opacity == 1
        assert regression.zorder == 10
        assert regression.legendgroup == point.legendgroup
        assert regression.showlegend is False
        assert point.marker.opacity == 0.72


def test_graph_scatter_alpha_only_fades_points_not_regression() -> None:
    result = graph(
        pd.DataFrame({"x": [1, 2, 3], "y": [2, 4, 6]}),
        x="x",
        y="y",
        graph="scatter",
        alpha=0.2,
        linear_regression=True,
        show=False,
    )

    assert result.figure is not None
    points, regression = result.figure.data
    assert points.opacity is None
    assert points.marker.opacity == 0.2
    assert regression.opacity == 1
    assert regression.zorder == 10


def test_graph_scatter_adds_regression_per_facet_and_colour_on_matching_axes() -> None:
    source = pd.DataFrame.from_records(
        {
            "x": x,
            "y": multiplier * x + offset,
            "group": group,
            "facet": facet,
        }
        for facet, multiplier in (("up", 1), ("down", -1))
        for group, offset in (("a", 0), ("b", 5))
        for x in (1, 2, 3)
    )

    result = graph(
        source,
        x="x",
        y="y",
        graph="scatter",
        group_colour="group",
        facet_col="facet",
        linear_regression=True,
        show=False,
    )

    assert result.figure is not None
    point_traces = [
        trace
        for trace in result.figure.data
        if trace.mode is not None and "markers" in trace.mode
    ]
    regression_traces = [
        trace
        for trace in result.figure.data
        if trace.name.startswith("Linear regression")
    ]
    point_axes = sorted(
        (trace.name, trace.xaxis, trace.yaxis) for trace in point_traces
    )
    regression_axes = sorted(
        (
            trace.name.removeprefix("Linear regression (").removesuffix(")"),
            trace.xaxis,
            trace.yaxis,
        )
        for trace in regression_traces
    )

    assert len(point_traces) == 4
    assert len(regression_traces) == 4
    assert all(len(trace.x) == 3 for trace in regression_traces)
    assert regression_axes == point_axes


# Density and remaining renderers


def test_graph_builds_one_and_two_dimensional_density() -> None:
    source = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0, 5.0],
            "y": [1.0, 4.0, 2.0, 5.0, 3.0],
        }
    )

    density_1d = graph(source, x="x", graph="density", show=False)
    density_2d = graph(source, x="x", y="y", graph="density", show=False)

    assert density_1d.figure is not None
    assert density_2d.figure is not None
    assert density_1d.figure.data[0].type == "scatter"
    assert density_1d.figure.data[0].fill == "tozeroy"
    assert density_2d.figure.data[0].type == "contour"


@pytest.mark.parametrize(
    "dtype", [np.int32, np.float32, np.uint32, "Int64", "Float32", "UInt64"]
)
def test_graph_density_supports_pandas_numeric_dtypes(dtype: object) -> None:
    source = pd.DataFrame({"value": pd.Series([1, 2, 3, 4, 5], dtype=dtype)})

    result = graph(source, x="value", graph="density", show=False)

    assert result.figure is not None
    assert len(result.figure.data) == 1
    assert result.data["value"].dtype == source["value"].dtype


def test_graph_density_drops_nullable_numeric_values() -> None:
    source = pd.DataFrame(
        {"value": pd.Series([1.0, 2.0, pd.NA, 4.0, 5.0], dtype="Float64")}
    )

    result = graph(source, x="value", graph="density", show=False)

    assert result.figure is not None
    assert len(result.figure.data) == 1
    assert result.data["value"].isna().sum() == 1


def test_graph_density_drops_nat_before_numeric_conversion() -> None:
    source = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-01", "2021-01-01", None, "2022-01-01"])}
    )

    result = graph(
        source,
        x="date",
        graph="density",
        convert_dates=False,
        show=False,
    )

    assert result.figure is not None
    plotted_dates = pd.to_datetime(result.figure.data[0].x)
    assert plotted_dates.min() > pd.Timestamp("2019-01-01")
    assert plotted_dates.max() < pd.Timestamp("2023-01-01")
    assert result.data["date"].isna().sum() == 1


def test_graph_density_drops_null_x_y_pairs_together() -> None:
    source = pd.DataFrame(
        {
            "x": [0.0, 1.0, 2.0, 3.0, 1_000_000_000.0, np.nan],
            "y": [0.0, 1.0, 4.0, 9.0, np.nan, 1_000_000_000.0],
        }
    )

    result = graph(source, x="x", y="y", graph="density", show=False)

    assert result.figure is not None
    assert len(result.figure.data) == 1
    assert max(result.figure.data[0].x) < 10
    assert max(result.figure.data[0].y) < 20


def test_graph_density_rejects_non_numeric_y() -> None:
    source = pd.DataFrame({"x": [1.0, 2.0, 3.0], "label": ["one", "two", "three"]})

    with pytest.raises(GraphConversionError, match="supported quantitative dtype"):
        graph(source, x="x", y="label", graph="density", show=False)


def test_graph_applies_alpha_to_density_and_area_traces() -> None:
    source = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "y": [1.0, 4.0, 2.0, 5.0, 3.0, 6.0],
            "group": ["a", "a", "a", "b", "b", "b"],
        }
    )

    density_1d = graph(source, x="x", graph="density", alpha=0.2, show=False)
    density = graph(source, x="x", y="y", graph="density", alpha=0.2, show=False)
    area = graph(
        source,
        x="x",
        y="y",
        graph="area",
        group_colour="group",
        alpha=0.2,
        show=False,
    )

    assert density_1d.figure is not None
    assert density.figure is not None
    assert area.figure is not None
    assert all(trace.opacity == 0.2 for trace in density_1d.figure.data)
    assert all(trace.opacity == 0.2 for trace in density.figure.data)
    assert all(trace.opacity == 0.2 for trace in area.figure.data)


def test_graph_density_rejects_singular_values() -> None:
    source = pd.DataFrame({"x": [1.0, 1.0, 1.0], "y": [2.0, 2.0, 2.0]})

    with pytest.raises(InsufficientGraphDataError, match="distinct x values"):
        graph(source, x="x", graph="density", show=False)

    with pytest.raises(InsufficientGraphDataError, match="distinct x values"):
        graph(source, x="x", y="y", graph="density", show=False)


def test_graph_builds_line_and_stacked_area_figures() -> None:
    source = pd.DataFrame(
        {
            "month": [2, 1, 2, 1],
            "segment": ["a", "a", "b", "b"],
            "value": [2, 1, 4, 3],
        }
    )

    line = graph(
        source,
        x="month",
        y="value",
        y_agg="sum",
        graph="line",
        group_colour="segment",
        show=False,
    )
    area = graph(
        source,
        x="month",
        y="value",
        y_agg="sum",
        graph="area",
        group_colour="segment",
        show=False,
    )

    assert line.figure is not None
    assert area.figure is not None
    assert len(line.figure.data) == 2
    assert all(trace.mode == "lines+markers" for trace in line.figure.data)
    assert len(area.figure.data) == 2
    assert [trace.fill for trace in area.figure.data] == ["tozeroy", "tonexty"]
    assert all(trace.stackgroup == "area" for trace in area.figure.data)
    assert [trace.hovertemplate for trace in area.figure.data] == [
        trace.hovertemplate for trace in line.figure.data
    ]
    assert all(
        trace.hovertemplate is not None
        and "<br>" in trace.hovertemplate
        and trace.hovertemplate.endswith("<extra></extra>")
        for trace in area.figure.data
    )


def test_graph_applies_renderer_specific_layout_polish() -> None:
    aggregate_source = pd.DataFrame({"x": [1, 1, 2, 2], "value": [1.0, 2.0, 3.0, 4.0]})
    timeline_source = pd.DataFrame(
        {
            "start": pd.date_range("2025-01-01", periods=20),
            "end": pd.date_range("2025-01-02", periods=20),
            "label": [f"row-{index}" for index in range(20)],
        }
    )

    histogram = graph(aggregate_source, x="x", graph="histogram", show=False)
    line = graph(
        aggregate_source,
        x="x",
        y="value",
        y_agg="mean",
        graph="line",
        show=False,
    )
    density = graph(aggregate_source, x="value", graph="density", show=False)
    timeline = graph(
        timeline_source,
        x="start",
        x_end="end",
        y="label",
        graph="timeline",
        convert_dates=False,
        show=False,
    )

    assert histogram.figure is not None
    assert line.figure is not None
    assert density.figure is not None
    assert timeline.figure is not None
    assert histogram.figure.layout.bargap == 0
    assert histogram.figure.layout.barcornerradius == 0
    assert line.figure.layout.hovermode == "x unified"
    assert line.figure.data[0].line.width == 2.4
    assert line.figure.data[0].marker.size == 6
    assert density.figure.layout.yaxis.title.text == "Density"
    assert density.figure.data[0].line.width == 2.25
    assert timeline.figure.layout.yaxis.autorange == "reversed"
    assert timeline.figure.layout.xaxis.showgrid is True
    assert timeline.figure.layout.yaxis.showgrid is False
    assert timeline.figure.layout.height == 540


# Strict dtype, aggregation, and data validation


def test_graph_exception_hierarchy_is_value_error_compatible() -> None:
    graph_errors = (
        GraphCapabilityError,
        GraphColumnError,
        GraphDataTypeError,
        GraphConversionError,
        GraphAggregationError,
        GraphDataError,
        TimelineDataError,
        InsufficientGraphDataError,
        GraphRenderingError,
        GraphExportError,
        GraphExportDependencyError,
    )

    assert all(issubclass(error_type, GraphingError) for error_type in graph_errors)
    assert issubclass(GraphingError, ValueError)
    assert issubclass(GraphConversionError, GraphDataTypeError)
    assert issubclass(TimelineDataError, GraphDataError)
    assert issubclass(InsufficientGraphDataError, GraphDataError)
    assert issubclass(GraphExportDependencyError, RuntimeError)


@pytest.mark.parametrize("graph_type", ["box", "violin"])
def test_distribution_graphs_convert_numeric_string_y_and_warn(
    graph_type: str, capsys: pytest.CaptureFixture[str]
) -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"], "value": ["1", "2", "3"]})

    result = graph(source, x="category", y="value", graph=graph_type, show=False)

    assert pd.api.types.is_integer_dtype(result.data["value"])
    assert result.data["value"].tolist() == [1, 2, 3]
    assert (
        "column 'value' converted from 'object' to 'int64'" in capsys.readouterr().out
    )


@pytest.mark.parametrize("graph_type", ["box", "violin"])
def test_distribution_graphs_reject_partially_non_numeric_y(graph_type: str) -> None:
    source = pd.DataFrame({"category": ["a", "a"], "value": ["1", "not-a-number"]})

    with pytest.raises(
        GraphConversionError, match="column 'value'.*quantitative"
    ) as error:
        graph(source, x="category", y="value", graph=graph_type, show=False)

    assert isinstance(error.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "values",
    [
        pd.Series([True, False], dtype="bool"),
        pd.Series([1 + 2j, 2 + 1j], dtype="complex128"),
        pd.Series(pd.date_range("2025-01-01", periods=2)),
    ],
)
def test_box_rejects_non_real_quantitative_dtypes(values: pd.Series) -> None:
    source = pd.DataFrame({"category": ["a", "b"], "value": values})

    with pytest.raises(GraphDataTypeError, match="quantitative y-axis"):
        graph(source, x="category", y="value", graph="box", show=False)


@pytest.mark.parametrize("graph_type", ["density", "scatter"])
def test_numeric_y_graphs_convert_numeric_strings(
    graph_type: str, capsys: pytest.CaptureFixture[str]
) -> None:
    source = pd.DataFrame({"x": [1, 2, 3], "y": ["2", "5", "3"]})

    result = graph(source, x="x", y="y", graph=graph_type, show=False)

    assert pd.api.types.is_integer_dtype(result.data["y"])
    assert "column 'y' converted" in capsys.readouterr().out


def test_scatter_rejects_categorical_y_even_without_regression() -> None:
    source = pd.DataFrame({"x": [1, 2, 3], "y": ["low", "middle", "high"]})

    with pytest.raises(GraphConversionError, match="column 'y'.*quantitative"):
        graph(
            source,
            x="x",
            y="y",
            graph="scatter",
            linear_regression=False,
            show=False,
        )


def test_quantitative_axes_convert_timedelta_strings() -> None:
    source = pd.DataFrame({"category": ["a", "a"], "duration": ["1 day", "2 days"]})

    result = graph(
        source,
        x="category",
        y="duration",
        graph="violin",
        convert_dates=False,
        show=False,
    )

    assert pd.api.types.is_timedelta64_dtype(result.data["duration"])


@pytest.mark.parametrize(
    ("y_agg", "expected"),
    [("sum", 4), ("mean", 2.0), ("median", 2.0)],
)
def test_measure_aggregations_convert_numeric_strings(
    y_agg: str, expected: float, capsys: pytest.CaptureFixture[str]
) -> None:
    source = pd.DataFrame({"category": ["a", "a"], "value": ["1", "3"]})

    result = graph(
        source,
        x="category",
        y="value",
        y_agg=y_agg,
        graph="bar",
        show=False,
    )

    assert result.data[f"{y_agg}_of_value"].iloc[0] == expected
    assert "column 'value' converted" in capsys.readouterr().out


def test_categorical_mode_uses_first_deterministic_pandas_mode() -> None:
    source = pd.DataFrame(
        {"category": ["a", "a", "a", "a"], "value": ["b", "a", "b", "a"]}
    )

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="mode",
        graph="bar",
        show=False,
    )

    assert result.data["mode_of_value"].tolist() == ["a"]


def test_y_aggregation_without_y_uses_x_as_measure() -> None:
    source = pd.DataFrame({"value": [1, 1, 2]})

    result = graph(source, x="value", y_agg="sum", graph="bar", show=False)

    assert result.data.to_dict("list") == {
        "value": [1, 2],
        "sum_of_value": [2, 2],
    }


@pytest.mark.parametrize(
    ("y_agg", "expected", "should_warn"),
    [
        ("count", [2, 1], False),
        ("countd", [1, 1], False),
        ("sum", [2, 2], True),
        ("mean", [1.0, 2.0], True),
        ("mode", [1, 2], True),
        ("median", [1.0, 2.0], True),
    ],
)
def test_histogram_supports_every_measure_aggregation_and_warns_when_clearer(
    y_agg: str,
    expected: list[float],
    should_warn: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = pd.DataFrame({"value": [1, 1, 2]})

    result = graph(source, x="value", y_agg=y_agg, graph="histogram", show=False)
    output = capsys.readouterr().out

    assert result.data[f"{y_agg}_of_value"].tolist() == expected
    assert (
        "a bar chart may present this measure more clearly" in output
    ) is should_warn


def test_numeric_measure_aggregation_rejects_categorical_values() -> None:
    source = pd.DataFrame(
        {
            "category": ["a", "a"],
            "value": pd.Series(["low", "high"], dtype="category"),
        }
    )

    with pytest.raises(GraphConversionError, match="sum measure.*column 'value'"):
        graph(
            source,
            x="category",
            y="value",
            y_agg="sum",
            graph="bar",
            show=False,
        )


def test_aggregate_preserves_y_used_as_colour_group() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"], "value": ["1", "2", "1"]})

    result = graph(
        source,
        x="category",
        y="value",
        y_agg="sum",
        group_colour="value",
        graph="bar",
        show=False,
    )

    assert result.group_colour == "value"
    assert result.data.columns.tolist() == ["category", "value", "sum_of_value"]
    assert pd.api.types.is_integer_dtype(result.data["value"])
    assert [trace.name for trace in result.figure.data] == ["1", "2"]


@pytest.mark.parametrize("x_agg", ["fortnight", True, np.complex128(1 + 1j)])
def test_graph_rejects_unknown_or_non_real_x_aggregations(x_agg: object) -> None:
    source = pd.DataFrame({"value": [1, 2, 3]})

    with pytest.raises(GraphAggregationError, match="Accepted|positive"):
        graph(
            source,
            x="value",
            x_agg=x_agg,  # type: ignore[arg-type]
            graph="bar",
            show=False,
        )


def test_graph_accepts_numpy_numeric_bin_width_and_returns_numeric_midpoints() -> None:
    source = pd.DataFrame({"value": [1, 2, 3]})

    result = graph(
        source,
        x="value",
        x_agg=np.int64(2),  # type: ignore[arg-type]
        graph="histogram",
        show=False,
    )

    assert result.data["value"].tolist() == [1.0, 3.0]
    assert pd.api.types.is_float_dtype(result.data["value"])
    assert list(result.figure.data[0].x) == [1.0, 3.0]


def test_graph_rejects_numeric_bins_for_timedelta_x() -> None:
    source = pd.DataFrame({"duration": pd.to_timedelta([1, 2, 3], unit="D")})

    with pytest.raises(GraphAggregationError, match="timedelta.*ambiguous"):
        graph(
            source,
            x="duration",
            x_agg=1,
            graph="histogram",
            convert_dates=False,
            show=False,
        )


def test_date_histogram_preserves_timezone_during_aggregation() -> None:
    source = pd.DataFrame(
        {"date": pd.date_range("2025-01-01", periods=3, tz="Europe/London")}
    )

    result = graph(
        source,
        x="date",
        x_agg="day",
        graph="histogram",
        convert_dates=False,
        show=False,
    )

    assert str(result.data["date"].dtype) == "datetime64[ns, Europe/London]"
    assert all(value.tzinfo is not None for value in result.data["date"])


def test_date_histogram_preserves_both_ambiguous_timezone_hours() -> None:
    source = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-10-26 01:30:00+00:00", "2025-10-26 00:30:00+00:00"]
            ).tz_convert("Europe/London")
        }
    )

    result = graph(
        source,
        x="date",
        x_agg="hour",
        graph="histogram",
        convert_dates=False,
        show=False,
    )

    utc_starts = set(result.data["date"].dt.tz_convert("UTC"))
    assert utc_starts == {
        pd.Timestamp("2025-10-26 00:00:00+00:00"),
        pd.Timestamp("2025-10-26 01:00:00+00:00"),
    }


def test_box_numeric_x_bins_preserve_rows() -> None:
    source = pd.DataFrame({"age": [1, 9, 11], "value": [2, 3, 4]})

    result = graph(
        source,
        x="age",
        x_agg=10,
        y="value",
        graph="box",
        show=False,
    )

    assert len(result.data) == 3
    assert result.data["age"].astype(str).tolist() == [
        "[0, 10)",
        "[0, 10)",
        "[10, 20)",
    ]


@pytest.mark.parametrize("graph_type", ["box", "violin"])
def test_distribution_date_x_bins_preserve_rows(graph_type: str) -> None:
    source = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-03", "2025-02-01"]),
            "value": [2, 3, 4],
        }
    )

    result = graph(
        source,
        x="date",
        x_agg="month",
        y="value",
        graph=graph_type,
        convert_dates=False,
        show=False,
    )

    assert len(result.data) == 3
    assert result.data["date"].tolist() == [
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-02-01"),
    ]


def test_timeline_convert_dates_false_requires_datetime_dtype() -> None:
    source = pd.DataFrame(
        {"start": ["2025-01-01"], "end": ["2025-01-02"], "episode": ["one"]}
    )

    with pytest.raises(GraphDataTypeError, match="convert_dates=False"):
        graph(
            source,
            x="start",
            x_end="end",
            y="episode",
            graph="timeline",
            convert_dates=False,
            show=False,
        )


def test_timeline_conversion_is_all_or_nothing() -> None:
    source = pd.DataFrame(
        {
            "start": ["2025-01-01", "not-a-date"],
            "end": ["2025-01-02", "2025-01-03"],
            "episode": ["one", "two"],
        }
    )

    with pytest.raises(GraphConversionError, match="x-axis column 'start'") as error:
        graph(
            source,
            x="start",
            x_end="end",
            y="episode",
            graph="timeline",
            show=False,
        )

    assert error.value.__cause__ is not None


def test_timeline_missing_dates_follow_discard_setting(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = pd.DataFrame(
        {
            "start": pd.to_datetime(["2025-01-01", None]),
            "end": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "episode": ["one", "two"],
        }
    )

    result = graph(
        source,
        x="start",
        x_end="end",
        y="episode",
        graph="timeline",
        discard_null_aggs=True,
        convert_dates=False,
        show=False,
    )

    assert len(result.data) == 1
    assert "discarded 1 row" in capsys.readouterr().out
    with pytest.raises(TimelineDataError, match="discard_null_aggs=True"):
        graph(
            source,
            x="start",
            x_end="end",
            y="episode",
            graph="timeline",
            discard_null_aggs=False,
            convert_dates=False,
            show=False,
        )


def test_timeline_rejects_reversed_ranges_but_accepts_equal_ranges() -> None:
    reversed_source = pd.DataFrame(
        {
            "start": pd.to_datetime(["2025-01-02"]),
            "end": pd.to_datetime(["2025-01-01"]),
            "episode": ["one"],
        }
    )
    equal_source = pd.DataFrame(
        {
            "start": pd.to_datetime(["2025-01-01"]),
            "end": pd.to_datetime(["2025-01-01"]),
            "episode": ["one"],
        }
    )

    with pytest.raises(TimelineDataError, match="before x values"):
        graph(
            reversed_source,
            x="start",
            x_end="end",
            y="episode",
            graph="timeline",
            convert_dates=False,
            show=False,
        )

    result = graph(
        equal_source,
        x="start",
        x_end="end",
        y="episode",
        graph="timeline",
        convert_dates=False,
        show=False,
    )
    assert result.figure is not None


def test_timeline_rejects_all_missing_ranges() -> None:
    source = pd.DataFrame(
        {
            "start": pd.to_datetime([None, None]),
            "end": pd.to_datetime([None, None]),
            "episode": ["one", "two"],
        }
    )

    with pytest.raises(TimelineDataError, match="no usable rows"):
        graph(
            source,
            x="start",
            x_end="end",
            y="episode",
            graph="timeline",
            convert_dates=False,
            show=False,
        )


def test_grouped_density_fails_if_any_group_is_insufficient() -> None:
    source = pd.DataFrame(
        {
            "value": [1.0, 2.0, 3.0, 1.0, 1.0, 1.0],
            "group": ["valid", "valid", "valid", "invalid", "invalid", "invalid"],
        }
    )

    with pytest.raises(InsufficientGraphDataError, match="group 'invalid'"):
        graph(
            source,
            x="value",
            group_colour="group",
            graph="density",
            show=False,
        )


def test_graph_wraps_anticipated_plotly_rendering_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = pd.DataFrame({"category": ["a", "b"]})

    def raise_plotly_value_error(*args: object, **kwargs: object) -> None:
        raise ValueError("invalid Plotly value")

    monkeypatch.setattr(
        "kraken.graphing.graphing_graphs._graph_bar", raise_plotly_value_error
    )

    with pytest.raises(GraphRenderingError, match="Graph 'bar'.*column") as error:
        graph(source, x="category", graph="bar", show=False)

    assert isinstance(error.value.__cause__, ValueError)


def test_non_default_irrelevant_renderer_options_warn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = pd.DataFrame({"category": ["a", "b"]})

    graph(
        source,
        x="category",
        graph="bar",
        bw_adjust=0.7,
        showfliers=False,
        linear_regression=True,
        show=False,
    )
    output = capsys.readouterr().out

    assert "bw_adjust does not apply" in output
    assert "showfliers does not apply" in output
    assert "linear_regression does not apply" in output


def test_default_irrelevant_renderer_options_do_not_warn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph(
        pd.DataFrame({"category": ["a", "b"]}),
        x="category",
        graph="bar",
        show=False,
    )

    assert "does not apply" not in capsys.readouterr().out


def test_graph_conversion_warnings_follow_readout_suppression(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = pd.DataFrame({"category": ["a", "b"], "value": ["1", "2"]})

    readout.suppress()
    try:
        graph(source, x="category", y="value", graph="box", show=False)
    finally:
        readout.activate()

    assert "converted" not in capsys.readouterr().out


# GraphResult compatibility and export


def test_graph_aggregation_mode_returns_data_without_figure() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"]})

    result = graph(source, x="category", graph="aggregation", show=False)

    assert result.figure is None
    assert result.data["count_of_category"].tolist() == [2, 1]


def test_graph_result_export_requires_a_figure(tmp_path: Path) -> None:
    result = graph(pd.DataFrame({"category": ["a", "b"]}), x="category", show=False)

    with pytest.raises(GraphExportError, match="no figure to export"):
        result.write_html(tmp_path / "graph.html")

    with pytest.raises(GraphExportError, match="no figure to export"):
        result.write_image(tmp_path / "graph.png")


def test_graph_show_and_return_results_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = pd.DataFrame({"category": ["a", "b"]})
    show_calls: list[tuple[go.Figure, dict[str, object]]] = []
    monkeypatch.setattr(
        go.Figure,
        "show",
        lambda figure, **kwargs: show_calls.append((figure, kwargs)),
    )

    with pytest.warns(DeprecationWarning, match="result.data"):
        result = graph(
            source,
            x="category",
            graph="bar",
            return_results=True,
            show=True,
        )

    assert show_calls == [
        (
            result.figure,
            {
                "config": {
                    "responsive": True,
                    "displaylogo": False,
                    "toImageButtonOptions": {"scale": 2},
                }
            },
        )
    ]

    graph(source, x="category", graph="bar", show=False)
    assert show_calls[0][0] is result.figure
    assert len(show_calls) == 1


def test_graph_preserves_legacy_positional_parameter_order() -> None:
    legacy_parameters = [
        "df",
        "x",
        "y",
        "graph",
        "x_agg",
        "y_agg",
        "group_colour",
        "where_clause",
        "convert_dates",
        "discard_null_aggs",
        "figsize",
        "bw_adjust",
        "alpha",
        "convert_categories_to_str",
        "linear_regression",
        "showfliers",
        "title",
        "x_label",
        "y_label",
        "return_results",
    ]
    parameters = inspect.signature(graph).parameters

    assert list(parameters)[: len(legacy_parameters)] == legacy_parameters
    assert all(
        parameters[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        for name in legacy_parameters
    )
    assert all(
        parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        for name in (
            "width",
            "height",
            "scroll",
            "show",
            "x_end",
            "facet_row",
            "facet_col",
            "marginal_x",
            "marginal_y",
            "hover_columns",
            "error",
            "confidence_level",
        )
    )


def test_graph_legacy_positional_values_are_not_reinterpreted() -> None:
    source = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0]})

    result = graph(
        source,
        "value",
        None,
        "density",
        None,
        None,
        None,
        None,
        True,
        True,
        None,
        0.5,
        0.25,
        False,
        False,
        True,
        None,
        None,
        None,
        False,
        show=False,
    )

    assert result.figure is not None
    assert result.figure.layout.width is None
    assert all(trace.opacity == 0.25 for trace in result.figure.data)


def test_graph_wrappers_preserve_legacy_slots_and_keyword_only_extensions() -> None:
    top_level = inspect.signature(graph).parameters
    result_parameters = inspect.signature(Result.graph).parameters
    list_parameters = inspect.signature(ResultList.graph).parameters

    top_level_names = list(top_level)
    assert list(result_parameters)[1:20] == top_level_names[1:20]
    assert list(list_parameters)[2:21] == top_level_names[1:20]
    for name in top_level_names[20:]:
        assert result_parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert list_parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
    assert top_level["linear_regression"].default is False
    assert result_parameters["linear_regression"].default is False
    assert list_parameters["linear_regression"].default is False
    assert (
        inspect.signature(prepare_graph).parameters["linear_regression"].default
        is False
    )


def test_result_graph_matches_top_level_contract() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"]})
    result = Result(source, df_name="example")

    top_level = graph(source, x="category", graph="bar", show=False)
    wrapped = result.graph(x="category", graph="bar", show=False)

    assert isinstance(wrapped, GraphResult)
    assert isinstance(wrapped.figure, go.Figure)
    pd.testing.assert_frame_equal(wrapped.data, top_level.data)


def test_result_list_graph_matches_top_level_contract() -> None:
    source = pd.DataFrame({"category": ["a", "a", "b"]})
    results = ResultList([Result(source, df_name="example")])

    top_level = graph(source, x="category", graph="line", show=False)
    wrapped = results.graph(df_name="example", x="category", graph="line", show=False)

    assert isinstance(wrapped, GraphResult)
    assert isinstance(wrapped.figure, go.Figure)
    pd.testing.assert_frame_equal(wrapped.data, top_level.data)


def test_graph_exports_standalone_interactive_html(tmp_path: Path) -> None:
    source = pd.DataFrame({"month": [1, 2, 3], "value": [2, 4, 3]})
    result = graph(
        source,
        x="month",
        y="value",
        y_agg="sum",
        graph="line",
        show=False,
    )
    output = tmp_path / "graph.html"

    assert result.write_html(output, include_plotlyjs=True) == output
    html = output.read_text(encoding="utf-8")

    assert output.stat().st_size > 1_000_000
    assert "Plotly.newPlot" in html
    assert "plotly.js" in html.lower()


def test_graph_result_writes_static_image_with_kaleido(tmp_path: Path) -> None:
    pytest.importorskip("kaleido")
    result = graph(
        pd.DataFrame({"month": [1, 2, 3], "value": [2, 4, 3]}),
        x="month",
        y="value",
        graph="line",
        show=False,
    )
    output = tmp_path / "graph.png"

    assert result.write_image(output) == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_graph_result_explains_missing_kaleido(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = GraphResult(figure=go.Figure(), data=pd.DataFrame())
    monkeypatch.setattr("kraken.graphing.models.find_spec", lambda name: None)

    with pytest.raises(
        GraphExportDependencyError, match="included as a Kraken core dependency"
    ):
        result.write_image(tmp_path / "graph.png")


def test_graph_result_explains_missing_chrome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = GraphResult(figure=go.Figure(), data=pd.DataFrame())
    monkeypatch.setattr("kraken.graphing.models.find_spec", lambda name: object())

    def raise_missing_chrome(
        figure: go.Figure, *args: object, **kwargs: object
    ) -> None:
        raise RuntimeError("Kaleido requires Google Chrome to be installed.")

    monkeypatch.setattr(go.Figure, "write_image", raise_missing_chrome)

    with pytest.raises(GraphExportDependencyError, match="plotly_get_chrome") as error:
        result.write_image(tmp_path / "graph.png")

    assert error.value.__cause__ is not None


def test_graph_result_wraps_anticipated_plotly_export_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = GraphResult(
        figure=go.Figure(), data=pd.DataFrame(), graph_type="bar", x="category"
    )
    monkeypatch.setattr("kraken.graphing.models.find_spec", lambda name: object())

    def raise_invalid_export(
        figure: go.Figure, *args: object, **kwargs: object
    ) -> None:
        raise ValueError("unsupported export option")

    monkeypatch.setattr(go.Figure, "write_html", raise_invalid_export)
    with pytest.raises(GraphExportError, match="exported to HTML") as html_error:
        result.write_html(tmp_path / "graph.html")
    assert isinstance(html_error.value.__cause__, ValueError)

    monkeypatch.setattr(go.Figure, "write_image", raise_invalid_export)
    with pytest.raises(
        GraphExportError, match="Accepted static image formats"
    ) as image_error:
        result.write_image(tmp_path / "graph.invalid")
    assert isinstance(image_error.value.__cause__, ValueError)


def test_graph_result_preserves_unrelated_export_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = GraphResult(figure=go.Figure(), data=pd.DataFrame())
    monkeypatch.setattr("kraken.graphing.models.find_spec", lambda name: object())

    def raise_write_error(figure: go.Figure, *args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(go.Figure, "write_image", raise_write_error)

    with pytest.raises(OSError, match="disk full"):
        result.write_image(tmp_path / "graph.png")
