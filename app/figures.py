"""Chart specifications for Plotly.js.

Each function returns {"data": [...], "layout": {...}} as plain lists and
numbers. Colours are named, not fixed: "token:chart-1" is replaced in the
browser by the --chart-1 colour of the interface theme, and "token:chart-1@0.2"
by the same colour at 20% opacity. Fonts, grid lines, margins and the legend
position are also applied in the browser (frontend/src/components/chart.tsx),
so every chart looks the same.
"""

SERIES = ["token:chart-1", "token:chart-2", "token:chart-3", "token:chart-4", "token:chart-5"]
INK = "token:chart-ink"
NEUTRAL = "token:chart-neutral"
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

USD = "US$ million"


def dates(months) -> list[str]:
    """Months as first-of-month dates, which Plotly places on a time axis."""
    return [f"{month}-01" for month in map(str, months)]


def line(x, y, name, color, *, dash=None, width=2, value_format=",.1f", suffix="", **extra) -> dict:
    return {
        "type": "scatter",
        "mode": "lines",
        "x": list(x),
        "y": list(y),
        "name": name,
        "line": {"color": color, "width": width, **({"dash": dash} if dash else {})},
        "hovertemplate": f"%{{y:{value_format}}}{suffix}",
        **extra,
    }


def bars(x, y, name, color, *, value_format=",.1f", suffix="", horizontal=False, **extra) -> dict:
    value = "x" if horizontal else "y"
    return {
        "type": "bar",
        "x": list(x),
        "y": list(y),
        "name": name,
        "orientation": "h" if horizontal else "v",
        "marker": {"color": color, "cornerradius": 4},
        "hovertemplate": f"%{{{value}:{value_format}}}{suffix}",
        **extra,
    }


def band(x, lower, upper, color, name) -> list[dict]:
    """A shaded interval between two bounds."""
    hidden = {"type": "scatter", "mode": "lines", "line": {"width": 0}, "hoverinfo": "skip"}
    return [
        {**hidden, "x": list(x), "y": list(upper), "showlegend": False},
        {
            **hidden,
            "x": list(x),
            "y": list(lower),
            "fill": "tonexty",
            "fillcolor": f"{color}@0.18",
            "name": name,
        },
    ]


def reference_line(value, *, horizontal=True, dash="dot") -> dict:
    span = {"x0": 0, "x1": 1, "xref": "paper", "y0": value, "y1": value}
    if not horizontal:
        span = {"y0": 0, "y1": 1, "yref": "paper", "x0": value, "x1": value}
    return {"type": "line", **span, "line": {"color": "token:chart-axis", "width": 1, "dash": dash}}


def figure(traces, *, y_title=None, x_title=None, **layout) -> dict:
    layout = dict(layout)
    if y_title:
        layout.setdefault("yaxis", {})["title"] = {"text": y_title}
    if x_title:
        layout.setdefault("xaxis", {})["title"] = {"text": x_title}
    return {"data": traces, "layout": layout}


def series_chart(months, values, name, *, y_title, color=SERIES[0], value_format=",.1f", suffix="",
                 zero_line=False) -> dict:
    """One series over time."""
    layout = {"showlegend": False}
    if zero_line:
        layout["shapes"] = [reference_line(0, dash="solid")]
    return figure(
        [line(dates(months), values, name, color, value_format=value_format, suffix=suffix)],
        y_title=y_title,
        **layout,
    )


def forecast_chart(history_months, history_values, forecast, model_name, *, interval_label) -> dict:
    """Observed values followed by a forecast, with its interval where the model has one."""
    x_history = dates(history_months)
    x_forecast = dates(forecast["months"])
    traces = []
    if forecast["lower"][0] is not None:
        traces += band(x_forecast, forecast["lower"], forecast["upper"], SERIES[1], interval_label)
    traces.append(line(x_history, history_values, "Observed", SERIES[0]))
    # The forecast line starts at the last observed point so the two lines join.
    traces.append(
        line(
            [x_history[-1], *x_forecast],
            [history_values[-1], *forecast["mean"]],
            f"Forecast ({model_name})",
            SERIES[1],
        )
    )
    return figure(
        traces,
        y_title=USD,
        shapes=[reference_line(x_history[-1], horizontal=False)],
    )


def actual_vs_predicted(months, actual, predicted, model_name, lower=None, upper=None) -> dict:
    x = dates(months)
    traces = []
    if lower and lower[0] is not None:
        traces += band(x, lower, upper, SERIES[0], "95% prediction interval")
    traces.append(line(x, actual, "Actual", INK, mode="lines+markers", marker={"size": 8, "color": INK}))
    traces.append(
        line(x, predicted, model_name, SERIES[0], mode="lines+markers",
             marker={"size": 8, "color": SERIES[0]})
    )
    return figure(traces, y_title=USD)


def ranked_bars(labels, values, *, highlight, x_title, value_format=",.1f", suffix="") -> dict:
    """Horizontal bars, largest value at the top as given; one bar may be highlighted."""
    colors = [SERIES[0] if label == highlight else NEUTRAL for label in labels]
    trace = bars(values, labels, "", colors, value_format=value_format, suffix=suffix, horizontal=True)
    trace["text"] = [f"{value:{value_format}}{suffix}" for value in values]
    trace["textposition"] = "outside"
    trace["cliponaxis"] = False
    return figure(
        [trace],
        x_title=x_title,
        showlegend=False,
        hovermode="closest",
        yaxis={"autorange": "reversed", "automargin": True},
        margin={"r": 64},
    )


def month_bars(values, *, y_title, baseline, value_format=".1f") -> dict:
    """Twelve bars, one per calendar month, drawn up or down from the baseline.

    Each bar's length is the distance from the baseline, so the chart does not
    need an axis cut off above zero. Months above the baseline are highlighted.
    """
    colors = [SERIES[0] if value > baseline else NEUTRAL for value in values]
    trace = bars(MONTH_LABELS, [value - baseline for value in values], "", colors)
    trace["base"] = baseline
    trace["customdata"] = list(values)
    trace["hovertemplate"] = f"%{{customdata:{value_format}}}"
    trace["text"] = [f"{value:{value_format}}" for value in values]
    trace["textposition"] = "outside"
    trace["cliponaxis"] = False
    low, high = min(values), max(values)
    pad = (high - low) * 0.2
    return figure(
        [trace],
        y_title=y_title,
        showlegend=False,
        hovermode="closest",
        shapes=[reference_line(baseline, dash="solid")],
        yaxis={"range": [low - pad, high + pad]},
    )


def heatmap(years, values, *, colorbar_title, diverging_around=None, value_format=",.0f") -> dict:
    """Years down, calendar months across. Diverging colours when a midpoint is given."""
    trace = {
        "type": "heatmap",
        "x": MONTH_LABELS,
        "y": [str(year) for year in years],
        "z": values,
        "xgap": 2,
        "ygap": 2,
        "hovertemplate": f"%{{x}} %{{y}}: %{{z:{value_format}}}<extra></extra>",
        "colorbar": {"title": {"text": colorbar_title, "side": "right"}, "thickness": 12, "outlinewidth": 0},
    }
    if diverging_around is None:
        trace["colorscale"] = "token:scale-sequential"
    else:
        flat = [value for row in values for value in row if value is not None]
        reach = max(abs(max(flat) - diverging_around), abs(min(flat) - diverging_around))
        trace["colorscale"] = "token:scale-diverging"
        trace["zmin"] = diverging_around - reach
        trace["zmax"] = diverging_around + reach
    return figure(
        [trace],
        showlegend=False,
        hovermode="closest",
        yaxis={"autorange": "reversed", "type": "category", "showgrid": False},
        xaxis={"type": "category", "showgrid": False, "side": "top"},
        margin={"t": 32, "b": 8},
    )


def lag_bars(correlations, threshold) -> dict:
    """Correlation at each lag; lags that are statistically significant are highlighted."""
    lags = [row["lag"] for row in correlations]
    values = [row["correlation"] for row in correlations]
    colors = [SERIES[0] if row["significant"] else NEUTRAL for row in correlations]
    trace = bars(lags, values, "", colors, value_format="+.2f")
    return figure(
        [trace],
        y_title="Correlation",
        x_title="Months the indicator leads remittances",
        showlegend=False,
        hovermode="closest",
        shapes=[reference_line(0, dash="solid"), reference_line(threshold), reference_line(-threshold)],
        xaxis={"dtick": 1},
        yaxis={"range": [-0.5, 0.5]},
    )
