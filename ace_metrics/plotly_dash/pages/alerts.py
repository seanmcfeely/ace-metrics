"""Alert page for Dash app.

All functions that generate charts will have a @callback decorator along
  with its input and output parameters. They also share the return type
  and an exception as described below. Also, double-clicking on any plot
  will automatically adjust the range of its y-axis. Some charts can
  have 2 plot views: `Default` for regular columns and `Critical`
  for more important columns.

Args:
    relayoutData: Contains layout changes such as hidden traces, or user
      interactions like zooming, resetting axes, etc.
    template_data: Plot template based on chosen theme and color mode.
    current_fig: Existing figure to update, if applicable.

Returns:
    An updated figure or the same figure if no changes are made.

Raises:
    PreventUpdate: If no update is required or possible.
"""

from typing import Dict, List, Union

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc
from plotly.subplots import make_subplots

from ace_metrics.plotly_dash.app import chart_config
from ace_metrics.plotly_dash.helpers import double_click_reset_y_range, fetch_data, to_fiscal_year, to_ordinal

dash.register_page(__name__, path="/")


def extended_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add more columns to the DataFrame."""
    df = df.copy(deep=True)
    df["total"] = df.drop("month", axis=1).sum(axis=1)
    df["exploitation+installation"] = df["exploitation"] + df["installation"]
    df["recon+weaponization"] = df["reconnaissance"] + df["weaponization"]
    df["actions_on_objectives"] = df["exfil"] + df["damage"]

    return df


def update_side_by_side_chart(
    relayoutData: Dict, current_fig: Dict, template: Dict, table: str, chart_title: str
) -> Union[Dict, go.Figure]:
    """Update or create a side-by-side chart based on provided data.

    Create two subplots with shared x-axis, one for general data and the
      other for business hours data.

    Args:
        table: The name of the table used to generate charts.
        chart_title: Title of the chart.
    """
    if not current_fig and relayoutData:
        df = extended_df(fetch_data([table], True)[table])
        df_bh = extended_df(fetch_data([f"{table}_BH"], True)[f"{table}_BH"])
        included_cols = [
            "month",
            "exploitation+installation",
            "command_and_control",
            "actions_on_objectives",
            "recon+weaponization",
            "false_positive",
            "exploitation",
            "installation",
            "exfil",
            "damage",
            "delivery",
            "policy_violation",
            "grayware",
            "weaponization",
            "reconnaissance",
        ]
        df = df[included_cols]
        df_bh = df_bh[included_cols]

        fig = make_subplots(
            rows=1,
            cols=2,
            shared_xaxes=True,
            subplot_titles=(
                f"{chart_title}",
                f"{chart_title} (Business Hours)",
            ),
            horizontal_spacing=0.037,
        )
        color = px.colors.qualitative.Light24
        for i, col in enumerate(df.columns[1:]):
            fig.add_trace(
                go.Scatter(
                    x=df["month"],
                    y=df[col],
                    mode="lines+markers",
                    name=col,
                    line=dict(color=color[i]),
                    legendgroup=f"group{i}",
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df_bh["month"],
                    y=df_bh[col],
                    mode="lines+markers",
                    name=col,
                    line=dict(color=color[i]),
                    legendgroup=f"group{i}",
                    showlegend=False,
                ),
                row=1,
                col=2,
            )
        fig.update_xaxes(range=[len(df.index) - 13, len(df.index) - 1])
        fig.update_yaxes(range=[0, df.tail(13).iloc[:, 1:].max().max()])
        fig.update_yaxes(range=[0, df_bh.tail(13).iloc[:, 1:].max().max()], row=1, col=2)

        number_of_months = len(df["month"])
        y1_min, y1_max, y2_min, y2_max = float("inf"), float("-inf"), float("inf"), float("-inf")
        y1_min_crit, y1_max_crit, y2_min_crit, y2_max_crit = float("inf"), float("-inf"), float("inf"), float("-inf")
        x_axis = fig.data[0]["x"]
        for trace in fig.data:
            x_values, y_values = trace["x"], trace["y"]
            for x, y in zip(x_values, y_values):
                if x_axis[number_of_months - 13] <= x <= x_axis[number_of_months - 1]:
                    if trace.legendgroup not in ["group0", "group2", "group3"]:  # Default View
                        if trace["showlegend"] is None:  # First subplot
                            y1_min = min(y1_min, y)
                            y1_max = max(y1_max, y)
                        else:
                            y2_min = min(y2_min, y)
                            y2_max = max(y2_max, y)
                    else:  # Critical View
                        if trace["showlegend"] is None:  # First subplot
                            y1_min_crit = min(y1_min_crit, y)
                            y1_max_crit = max(y1_max_crit, y)
                        else:
                            y2_min_crit = min(y2_min_crit, y)
                            y2_max_crit = max(y2_max_crit, y)
        buttons = [
            dict(
                method="update",
                label="Default",
                args=[
                    {
                        "visible": [
                            True if trace.legendgroup not in ["group0", "group2", "group3"] else "legendonly"
                            for trace in fig.data
                        ],
                    },
                    {
                        "xaxis.range[0]": number_of_months - 13,
                        "xaxis2.range[0]": number_of_months - 13,
                        "xaxis.range[1]": number_of_months - 1,
                        "xaxis2.range[1]": number_of_months - 1,
                        "yaxis.range[0]": y1_min,
                        "yaxis2.range[0]": y2_min,
                        "yaxis.range[1]": y1_max,
                        "yaxis2.range[1]": y2_max,
                    },
                ],
            ),
            dict(
                method="update",
                label="Critical",
                args=[
                    {
                        "visible": [
                            True if trace.legendgroup in ["group0", "group1", "group2", "group3"] else "legendonly"
                            for trace in fig.data
                        ],
                    },
                    {
                        "xaxis.range[0]": number_of_months - 13,
                        "xaxis2.range[0]": number_of_months - 13,
                        "xaxis.range[1]": number_of_months - 1,
                        "yaxis.range[0]": y1_min_crit,
                        "yaxis2.range[0]": y2_min_crit,
                        "yaxis.range[1]": y1_max_crit,
                        "yaxis2.range[1]": y2_max_crit,
                    },
                ],
            ),
        ]

        fig.update_annotations(yshift=60)
        fig.update_layout(
            updatemenus=[dict(type="buttons", direction="left", x=0.5, xanchor="center", y=1.27, buttons=buttons)],
            legend={
                "title_text": "",
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": 1.18,
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin=dict(t=114, l=0, r=0, b=0),
            template=template,
        )

        fig.update_yaxes(title_text="hours", row=1, col=1)

        return fig

    if current_fig and relayoutData == {}:
        # Update the y-axis range
        current_fig["layout"]["yaxis"]["range"], current_fig["layout"]["yaxis2"]["range"] = double_click_reset_y_range(
            current_fig["data"], current_fig["layout"], True
        )

        return current_fig

    raise dash.exceptions.PreventUpdate


layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(id="alert-count", config=chart_config, style={"height": 405}),
                    ],
                    width={"size": 12, "order": "last", "offset": 0},
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(
                            id="yearly-alert-rank",
                            config=chart_config,
                            style={"height": 405},
                        ),
                    ],
                    width={"size": 6, "order": "last", "offset": 0},
                ),
                dbc.Col(
                    [
                        dcc.Graph(
                            id="alert-sla",
                            config=chart_config,
                            style={"height": 405},
                        ),
                    ],
                    width={"size": 6, "order": "last", "offset": 0},
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(id="alert-by-analyst", config=chart_config, style={"height": 405}),
                    ],
                    width={"size": 6, "order": "last", "offset": 0},
                ),
                dbc.Col(
                    [
                        dcc.Graph(id="alert-count-by-type", config=chart_config, style={"height": 405}),
                    ],
                    width={"size": 6, "order": "last", "offset": 0},
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(id="total-open-time", config=chart_config, style={"height": 480}),
                    ],
                    width={"size": 12, "order": "last", "offset": 0},
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(id="avg-time-to-dispo", config=chart_config, style={"height": 480}),
                    ],
                    width={"size": 12, "order": "last", "offset": 0},
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(id="std-time-to-dispo", config=chart_config, style={"height": 480}),
                    ],
                    width={"size": 12, "order": "last", "offset": 0},
                ),
            ],
            className="mb-3",
        ),
    ]
)


@callback(
    Output("alert-count", "figure"),
    [Input("alert-count", "relayoutData"), Input("theme-template-store", "data")],
    [State("alert-count", "figure")],
)
def update_alert_count(relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict) -> Union[go.Figure, Dict]:
    """Update or create a monthly alert count line chart."""
    if not current_fig and relayoutData:
        df = extended_df(fetch_data(["alert_count"], True)["alert_count"])
        df = df[
            [
                "month",
                "total",
                "exploitation+installation",
                "command_and_control",
                "actions_on_objectives",
                "recon+weaponization",
                "false_positive",
                "exploitation",
                "installation",
                "exfil",
                "damage",
                "delivery",
                "policy_violation",
                "grayware",
                "weaponization",
                "reconnaissance",
                # "reviewed",
                # "unknown",
            ]
        ]

        fig = px.line(
            df,
            x="month",
            y=df.columns[1:],
            labels={"value": "alert count"},
            title="Monthly Alert Counts",
            range_x=[len(df["month"]) - 61, len(df["month"]) - 1],  # 60 months back of data for default view
            range_y=[0, df.tail(61).iloc[:, 1].max().max()],
            template=template_data["template"],
        )

        buttons = [
            dict(
                method="restyle",
                label="Default",
                args=[
                    {
                        "visible": [
                            True
                            if x
                            not in [
                                "exploitation+installation",
                                "command_and_control",
                                "actions_on_objectives",
                                "recon+weaponization",
                            ]
                            else "legendonly"
                            for x in df.columns[1:]
                        ]
                    }
                ],
            ),
            dict(
                method="restyle",
                label="Critical",
                args=[
                    {
                        "visible": [
                            True
                            if x
                            in [
                                "exploitation+installation",
                                "command_and_control",
                                "actions_on_objectives",
                                "recon+weaponization",
                            ]
                            else "legendonly"
                            for x in df.columns[1:]
                        ]
                    }
                ],
            ),
        ]

        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    direction="left",
                    x=1.023,
                    xanchor="left",
                    y=-0.05,
                    buttons=buttons,
                )
            ],
            legend={"title_text": ""},
            margin=dict(t=43, l=0),
        )

        for trace in fig.data:
            trace.mode = "lines+markers"
            trace.marker = dict(size=5, color=trace.line.color)

        return fig

    if current_fig and relayoutData == {}:
        current_fig["layout"]["yaxis"]["range"] = double_click_reset_y_range(current_fig["data"], current_fig["layout"])
        return current_fig

    raise dash.exceptions.PreventUpdate


@callback(
    Output("yearly-alert-rank", "figure"),
    [Input("yearly-alert-rank", "relayoutData"), Input("theme-template-store", "data")],
    [State("yearly-alert-rank", "figure")],
)
def update_yearly_alert_ranks(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> Union[Dict, go.Figure]:
    """Update or create bar charts to rank alert types over a period."""

    def _create_plot(selected_columns: List[str]):
        df = extended_df(fetch_data(["alert_count"], True)["alert_count"]).set_index("month")
        last_6_months = df.tail(6).sum()
        last_6_months.name = "last_6_months"
        last_12_months = df.tail(12).sum()
        last_12_months.name = "last_12_months"

        df["fiscal_year"] = df.index.astype(str).to_series().apply(to_fiscal_year)
        df = df.groupby("fiscal_year").sum()
        df = df.append([last_6_months, last_12_months])

        df = df[selected_columns].T
        sorted_df = pd.DataFrame()

        for year_time in df.columns:
            temp_df = df.sort_values(by=year_time, ascending=False).reset_index()
            temp_df["rank"] = temp_df.index.map(lambda x: f"{to_ordinal(x+1)}")
            temp_df = temp_df.rename(columns={"index": f"alert_type_{year_time}"})
            temp_df = temp_df[["rank", f"alert_type_{year_time}", year_time]]

            if sorted_df.empty:
                sorted_df = temp_df
            else:
                sorted_df = pd.merge(sorted_df, temp_df, on="rank", how="outer")
        # Create the figure
        fig = go.Figure()
        for year_time in df.columns:
            fig.add_trace(
                go.Bar(
                    x=sorted_df["rank"],
                    y=sorted_df[year_time],
                    name=f"{year_time}",
                    text=sorted_df[f"alert_type_{year_time}"],
                    hoverinfo="y+text",
                )
            )

        buttons = [
            dict(method="relayout", label=option, args=[{"xaxis.title": option}]) for option in ["Default", "Critical"]
        ]
        fig.update_layout(
            title="Yearly Alert Disposition Rankings (Excl. FPs)",
            xaxis_title="rank",
            yaxis_title="alert count",
            barmode="group",
            xaxis={"range": [-0.5, 4.5]} if "reconnaissance" in selected_columns else {"range": [-0.5, 3.5]},
            updatemenus=[
                dict(
                    active=0 if "reconnaissance" in selected_columns else 1,
                    direction="left",
                    type="buttons",
                    x=0.75,
                    xanchor="left",
                    y=-0.07,
                    buttons=buttons,
                )
            ],
            legend={
                "x": 1,
                "xanchor": "right",
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin=dict(t=55, l=0, r=0, b=55),
            template=template_data["template"],
        )
        for i, trace in enumerate(fig.data):
            if trace.name in ["last_12_months", df.columns[-4]]:
                trace.visible = True
            else:
                trace.visible = "legendonly"

        return fig

    critical_columns = ["exploitation+installation", "recon+weaponization", "actions_on_objectives", "delivery"]
    default_columns = [
        col
        for col in extended_df(fetch_data(["alert_count"], True)["alert_count"]).columns.drop(
            ["total", "month", "false_positive"]
        )
        if col not in critical_columns
    ]
    selected_columns = default_columns

    if current_fig and relayoutData and "xaxis.title" in relayoutData:
        plot_type = relayoutData["xaxis.title"]
        if plot_type == "Default":
            selected_columns = default_columns
        else:
            selected_columns = critical_columns
        return _create_plot(selected_columns)

    if not current_fig and relayoutData:
        return _create_plot(selected_columns)

    if current_fig and relayoutData == {}:
        current_fig["layout"]["yaxis"]["autorange"] = True
        current_fig["layout"]["xaxis"]["range"] = (
            [-0.5, 4.5] if "reconnaissance" in current_fig["data"][0]["text"] else [-0.5, 3.5]
        )
        return current_fig
    raise dash.exceptions.PreventUpdate


@callback(
    Output("alert-sla", "figure"),
    [Input("alert-sla", "relayoutData"), Input("theme-template-store", "data")],
    [State("alert-sla", "figure")],
)
def update_alert_sla(relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict) -> Union[go.Figure, Dict]:
    """Update or create a monthly alerts SLA line chart."""
    if not current_fig and relayoutData:
        df = fetch_data(["overall_operating_alert"], True)["overall_operating_alert"].set_index("month")
        df = df[["bh_cycletime_avg", "real_cycletime_avg"]]
        fig = px.line(
            df,
            x=df.index,
            y=df.columns,
            labels={"value": ""},
            title="Monthly Alerts SLA",
            range_x=[len(df.index) - 25, len(df.index) - 1],
            range_y=[0, df.tail(25).max().max()],
        )

        fig.update_layout(
            legend=dict(
                x=0,
                y=1.1,
                traceorder="normal",
                orientation="h",
                title=dict(text=""),
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(t=55, l=0, r=0, b=0),
            template=template_data["template"],
        )

        for trace in fig.data:
            if trace.name == "bh_cycletime_avg":
                trace.name = "Average Business Cycle-Time (SLA)"
            else:
                trace.name = "Average Raw Cycle-Time"
            trace.mode = "lines+markers"
            trace.marker = dict(size=5, color=trace.line.color)

        return fig

    if current_fig and relayoutData == {}:
        current_fig["layout"]["yaxis"]["range"] = double_click_reset_y_range(current_fig["data"], current_fig["layout"])
        return current_fig

    raise dash.exceptions.PreventUpdate


@callback(
    Output("alert-by-analyst", "figure"),
    [Input("alert-by-analyst", "relayoutData"), Input("theme-template-store", "data")],
    [State("alert-by-analyst", "figure")],
)
def update_alert_by_analyst(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> Union[Dict, go.Figure]:
    """Update or create a line chart for alerts dispo'ed by analyst."""
    if not current_fig and relayoutData:
        df = fetch_data(["analyst_alert_quantities"], True)["analyst_alert_quantities"].set_index("month")
        df.sort_index(inplace=True)

        # Drop inactive users since last year
        sum_last_12_months = df.tail(12).sum()
        df.drop(columns=sum_last_12_months[sum_last_12_months == 0].index.tolist(), inplace=True)

        fig = px.line(
            df,
            x=df.index,
            y=df.columns,
            labels={"value": "alert count"},
            title="Alert Quantities by Analyst",
            range_x=[len(df.index) - 13, len(df.index) - 1],  # 12 months back of data for default view
            range_y=[0, df.tail(13).max().max()],
        )

        fig.update_layout(
            legend={
                "title_text": "",
                "orientation": "h",
                "y": 1.18,
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin=dict(t=100, l=0, r=0, b=0),
            template=template_data["template"],
        )
        return fig

    if current_fig and relayoutData == {}:
        current_fig["layout"]["yaxis"]["range"] = double_click_reset_y_range(current_fig["data"], current_fig["layout"])
        return current_fig

    raise dash.exceptions.PreventUpdate


@callback(
    Output("alert-count-by-type", "figure"),
    [Input("alert-count-by-type", "relayoutData"), Input("theme-template-store", "data")],
    [State("alert-count-by-type", "figure")],
)
def update_alert_count_by_type(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> Union[go.Figure, Dict]:
    """Update or create a line chart for alert quantities by type."""
    if not current_fig and relayoutData:
        df = fetch_data(["alert_type_quantities"], True)["alert_type_quantities"].set_index("month")
        df.sort_index(inplace=True)

        fig = px.line(
            df,
            x=df.index,
            y=df.columns,
            labels={"value": "alert count"},
            title="Alert Type Category Quantities",
            range_x=[len(df.index) - 13, len(df.index) - 1],  # 12 months back of data for default view
            range_y=[0, df.tail(13).max().max()],
            template=template_data["template"],
        )

        fig.update_layout(
            legend={
                "title_text": "",
                "orientation": "h",
                "y": 1.18,
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin=dict(t=100, l=0, r=0, b=0),
        )
        return fig

    if current_fig and relayoutData == {}:
        current_fig["layout"]["yaxis"]["range"] = double_click_reset_y_range(current_fig["data"], current_fig["layout"])
        return current_fig

    raise dash.exceptions.PreventUpdate


@callback(
    Output("total-open-time", "figure"),
    [Input("total-open-time", "relayoutData"), Input("theme-template-store", "data")],
    [State("total-open-time", "figure")],
)
def update_total_open_time(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> Union[Dict, go.Figure]:
    """Generate Total Open Time chart."""
    return update_side_by_side_chart(
        relayoutData, current_fig, template_data["template"], "cycle_time_sum", "Total Open Time"
    )


@callback(
    Output("avg-time-to-dispo", "figure"),
    [Input("avg-time-to-dispo", "relayoutData"), Input("theme-template-store", "data")],
    [State("avg-time-to-dispo", "figure")],
)
def update_avg_time_to_dispo(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> Union[Dict, go.Figure]:
    """Generate Average Time to Disposition chart."""
    return update_side_by_side_chart(
        relayoutData, current_fig, template_data["template"], "cycle_time_mean", "Average Time to Disposition"
    )


@callback(
    Output("std-time-to-dispo", "figure"),
    [Input("std-time-to-dispo", "relayoutData"), Input("theme-template-store", "data")],
    [State("std-time-to-dispo", "figure")],
)
def update_std_time_to_dispo(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> Union[Dict, go.Figure]:
    """Generate Standard Deviation for Time to Disposition chart."""
    return update_side_by_side_chart(
        relayoutData,
        current_fig,
        template_data["template"],
        "cycle_time_std",
        "Standard Deviation for Time to Disposition",
    )
