from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pandas import DataFrame

from kraken.exceptions import GraphExportDependencyError, GraphExportError

if TYPE_CHECKING:
    from plotly.graph_objects import Figure  # type: ignore[import-untyped]


GraphType = Literal[
    "aggregation",
    "density",
    "histogram",
    "bar",
    "box",
    "violin",
    "scatter",
    "stacked",
    "line",
    "area",
    "timeline",
]
AggregationMode = Literal["numeric", "non-numeric", "replace"]
AxisDomain = Literal["any", "quantitative", "quantitative_or_temporal", "temporal"]
HoverMode = Literal["none", "group", "row"]
ConfidenceIntervalMode = Literal["none", "data", "figure"]


def _is_missing_browser_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        error_name = type(current).__name__.lower()
        message = str(current).lower()
        if "chromenotfound" in error_name or (
            ("chrome" in message or "chromium" in message)
            and any(word in message for word in ("install", "not found", "requires"))
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


@dataclass(frozen=True)
class GraphSettings:
    x_domain: AxisDomain
    y_domain: AxisDomain | None
    y_mandatory: bool
    x_agg_mode: AggregationMode | Literal[False]
    y_agg: bool
    groups_supported: tuple[str, ...]
    facets: bool
    marginals: bool
    hover: HoverMode
    confidence_intervals: ConfidenceIntervalMode
    regression: bool


@dataclass(frozen=True)
class PreparedGraph:
    data: DataFrame
    plot_data: DataFrame
    graph_type: GraphType
    graph_mode: bool
    settings: GraphSettings
    x: str
    x_end: str | None
    y: str | None
    group_colour: str | None
    colour_on: str | None
    facet_row: str | None = None
    facet_col: str | None = None
    marginal_x: str | None = None
    marginal_y: str | None = None
    hover_columns: tuple[str, ...] = ()
    linear_regression: bool = False
    error: str | None = None
    error_lower: str | None = None
    error_upper: str | None = None
    error_plus: str | None = None
    error_minus: str | None = None


@dataclass(frozen=True)
class GraphResult:
    figure: "Figure | None"
    data: DataFrame
    graph_type: GraphType | None = None
    x: str | None = None
    x_end: str | None = None
    y: str | None = None
    group_colour: str | None = None
    facet_row: str | None = None
    facet_col: str | None = None
    marginal_x: str | None = None
    marginal_y: str | None = None
    hover_columns: tuple[str, ...] = ()
    error: str | None = None
    error_lower: str | None = None
    error_upper: str | None = None
    error_plus: str | None = None
    error_minus: str | None = None

    def __repr__(self) -> str:
        figure_type = type(self.figure).__name__ if self.figure is not None else None
        details = [
            f"graph_type={self.graph_type!r}",
            f"figure={figure_type!r}",
            f"shape={self.data.shape!r}",
            f"x={self.x!r}",
            f"y={self.y!r}",
        ]
        if self.group_colour is not None:
            details.append(f"group_colour={self.group_colour!r}")
        return f"GraphResult({', '.join(details)})"

    def _figure_or_raise(self) -> "Figure":
        if self.figure is None:
            raise GraphExportError(
                f"Graph '{self.graph_type or 'aggregation'}' has no figure to export; "
                "only rendered graph types can be exported."
            )
        return self.figure

    def write_html(self, path: str | Path, **kwargs: object) -> Path:
        output_path = Path(path).expanduser()
        try:
            self._figure_or_raise().write_html(output_path, **kwargs)
        except GraphExportError:
            raise
        except (TypeError, ValueError) as exc:
            raise GraphExportError(
                f"Graph '{self.graph_type}' could not be exported to HTML at "
                f"'{output_path}'. Use a valid path and Plotly write_html options."
            ) from exc
        return output_path

    def write_image(self, path: str | Path, **kwargs: object) -> Path:
        output_path = Path(path).expanduser()
        figure = self._figure_or_raise()
        if find_spec("kaleido") is None:
            raise GraphExportDependencyError(
                "Static image export requires Kaleido, which is included as a Kraken "
                "core dependency. Reinstall Kraken or install 'kaleido>=1.1,<2'."
            )
        try:
            figure.write_image(output_path, **kwargs)
        except Exception as exc:
            if _is_missing_browser_error(exc):
                raise GraphExportDependencyError(
                    "Static image export requires a compatible Chrome or Chromium "
                    "installation. Install a supported browser or run "
                    "'plotly_get_chrome' (or plotly.io.get_chrome() from Python)."
                ) from exc
            if isinstance(exc, (TypeError, ValueError)):
                raise GraphExportError(
                    f"Graph '{self.graph_type}' could not be exported to "
                    f"'{output_path}'. Accepted static image formats include PNG, "
                    "JPEG, WebP, SVG, and PDF."
                ) from exc
            raise
        return output_path
