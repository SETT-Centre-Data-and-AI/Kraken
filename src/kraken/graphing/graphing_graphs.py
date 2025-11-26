import pandas as pd
import seaborn as sns


def graph_bar(
    df: pd.DataFrame,
    x: str,
    y: str | None = None,
    group_colour: str | None = None,
    colour_on: str | None = None,
    alpha: float | None = 1,
) -> None:
    if colour_on:
        group_colour = colour_on
    if group_colour and pd.api.types.is_numeric_dtype(df[group_colour].dtype):
        df[group_colour] = df[group_colour].astype("category")
    if df[x].dtype == "datetime64[ns]":
        df[x] = pd.to_datetime(df[x]).dt.strftime("%d %b %Y")
    sns.barplot(data=df, x=x, y=y, hue=group_colour, alpha=alpha)
    return None


def graph_stacked(
    df: pd.DataFrame,
    x: str,
    y: str | None = None,
    group_colour: str | None = None,
    colour_on: str | None = None,
    alpha: float | None = 1,
) -> None:
    x_is_date = None
    if colour_on:
        group_colour = colour_on
    if group_colour and pd.api.types.is_numeric_dtype(df[group_colour].dtype):
        df[group_colour] = df[group_colour].astype("category")
    if df[x].dtype == "datetime64[ns]":
        x_is_date = True
        df[x] = pd.to_datetime(df[x]).dt.strftime("%Y%m%d")

    # Fill any missing group_colour/x category combinations with 0 and apply group sorting
    all_combinations = pd.MultiIndex.from_product(
        [df[x].unique(), df[group_colour].unique()],  # type: ignore
        names=[x, group_colour],
    ).to_frame(index=False)
    df = all_combinations.merge(df, on=[x, group_colour], how="left").fillna({y: 0})

    order = sorted(df[group_colour].unique())
    df = df.sort_values(by=[x, group_colour])  # type: ignore[list-item]

    # Reformat dates following sorting if applicable
    if x_is_date:
        df[x] = pd.to_datetime(df[x], format="%Y%m%d").dt.strftime("%d %b %Y")

    bottoms = pd.Series(0.0, index=df[x].unique())

    # Dynamically generate the colour palette based on the number of categories
    palette = sns.color_palette(n_colors=len(order))

    for i, category in enumerate(order):
        subset = df[df[group_colour] == category]
        sns.barplot(
            x=subset[x],
            y=subset[y],
            data=subset,
            label=category,
            alpha=alpha,
            color=palette[i],
            bottom=bottoms.loc[subset[x]].values,
        )
        bottoms.loc[subset[x]] += subset[y].values

    return None


def graph_density(
    df: pd.DataFrame,
    x: str,
    y: str | None = None,
    group_colour: str | None = None,
    bw_adjust: float = 0.5,
    alpha: float | None = None,
) -> None:
    hue = group_colour if group_colour else None
    if y:
        alpha = alpha if alpha else 1
        sns.kdeplot(
            data=df,
            x=x,
            y=y,
            fill=True,
            bw_adjust=bw_adjust,
            warn_singular=False,
            hue=group_colour,
            levels=20,
            alpha=alpha,
        )
    else:
        alpha = alpha if alpha else 0.5
        sns.kdeplot(
            df,
            x=x,
            fill=True,
            bw_adjust=bw_adjust,
            warn_singular=False,
            hue=hue,
            alpha=alpha,
        )
    return None


def graph_box(
    df: pd.DataFrame,
    x: str,
    y: str | None = None,
    group_colour: str | None = None,
    colour_on: str | None = None,
    showfliers: bool = True,
) -> None:
    x_is_date = None
    if df[x].dtype == "datetime64[ns]":
        x_is_date = True
        df[x] = pd.to_datetime(df[x]).dt.strftime("%Y%m%d")

    df = df.sort_values(by=[x])

    hue = group_colour if group_colour else colour_on if colour_on else None
    if hue and pd.api.types.is_numeric_dtype(df[hue].dtype):
        df[hue] = df[hue].astype("category")

    if x_is_date:
        df[x] = pd.to_datetime(df[x], format="%Y%m%d").dt.strftime("%d %b %Y")

    sns.boxplot(data=df, x=x, y=y, hue=hue, showfliers=showfliers)
    return None


def graph_violin(
    df: pd.DataFrame,
    x: str,
    y: str | None = None,
    group_colour: str | None = None,
    colour_on: str | None = None,
    alpha: float | None = 1,
) -> None:
    x_is_date = None
    if df[x].dtype == "datetime64[ns]":
        x_is_date = True
        df[x] = pd.to_datetime(df[x]).dt.strftime("%Y%m%d")

    df = df.sort_values(by=[x])

    hue = group_colour if group_colour else colour_on if colour_on else None
    if group_colour and pd.api.types.is_numeric_dtype(df[group_colour].dtype):
        df[group_colour] = df[group_colour].astype("category")

    if x_is_date:
        df[x] = pd.to_datetime(df[x], format="%Y%m%d").dt.strftime("%d %b %Y")

    sns.violinplot(data=df, x=x, y=y, hue=hue, alpha=alpha)
    return None


def graph_scatter(
    df: pd.DataFrame,
    x: str,
    y: str | None = None,
    group_colour: str | None = None,
    colour_on: str | None = None,
    alpha: float | None = 1,
    lr: bool = True,
) -> None:
    hue = group_colour if group_colour else colour_on if colour_on else None
    sns.scatterplot(data=df, x=x, y=y, hue=hue, marker="o", alpha=alpha)
    if lr:
        sns.regplot(
            data=df,
            x=x,
            y=y,
            scatter=False,
            line_kws={"color": "r", "alpha": 0.7, "lw": 1},
        )
    return None
