from collections import namedtuple

# Settings
GraphSettings = namedtuple(
    "GraphSettings",
    [
        "x_in_num",  # Boll: does x have to be numeric?
        "x_out_num",  # Bool: plot x as numeric
        "y_accepted",  # Bool: is y accepted?
        "y_mandatory",  # Bool: is y mandatory?
        "x_agg_mode",  # 'numeric' | 'replace' | False:  x aggregation accepted. numeric will calculate mid point, non-numeric will group as a category, and replace will transform values without grouping
        "y_agg",  # is y aggregation accepted?
        "groups_supported",
    ],
)

graph_list = {
    "aggregation": GraphSettings(
        x_in_num=False,
        x_out_num=False,
        y_accepted=True,
        y_mandatory=False,
        x_agg_mode="non-numeric",
        y_agg=True,
        groups_supported=["colour"],
    ),
    "density": GraphSettings(
        x_in_num=True,
        x_out_num=True,
        y_accepted=True,
        y_mandatory=False,
        x_agg_mode=False,
        y_agg=False,
        groups_supported=["colour"],
    ),
    "bar": GraphSettings(
        x_in_num=False,
        x_out_num=False,
        y_accepted=True,
        y_mandatory=False,
        x_agg_mode="non-numeric",
        y_agg=True,
        groups_supported=["colour"],
    ),
    "box": GraphSettings(
        x_in_num=False,
        x_out_num=False,
        y_accepted=True,
        y_mandatory=True,
        x_agg_mode="replace",
        y_agg=False,
        groups_supported=["colour"],
    ),
    "violin": GraphSettings(
        x_in_num=False,
        x_out_num=False,
        y_accepted=True,
        y_mandatory=True,
        x_agg_mode="replace",
        y_agg=False,
        groups_supported=["colour"],
    ),
    "scatter": GraphSettings(
        x_in_num=True,
        x_out_num=True,
        y_accepted=True,
        y_mandatory=True,
        x_agg_mode=False,
        y_agg=False,
        groups_supported=["colour"],
    ),
    "stacked": GraphSettings(
        x_in_num=False,
        x_out_num=False,
        y_accepted=True,
        y_mandatory=False,
        x_agg_mode="non-numeric",
        y_agg=True,
        groups_supported=["colour"],
    ),
}

dtype_list_is_numeric = {
    "float64": True,
    "int64": True,
    "Int64": True,
    "datetime64[ns]": True,
    "timedelta": True,
    "object": False,
    "bool": False,
    "category": False,
}

x_aggs_supported_date = {
    "minute": "T",
    "hour": "H",
    "day": "D",
    "month": "M",
    "year": "Y",
}
y_aggs_supported = {"count", "countd", "sum", "mean", "mode", "median"}
