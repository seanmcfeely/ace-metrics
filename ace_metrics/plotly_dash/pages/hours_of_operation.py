"""Hours of operations page for Dash app.

All functions that generate charts will have a @callback decorator along
  with its input and output parameters. They also share the return type
  and an exception as described below.

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

from ace_metrics.plotly_dash.app import chart_config
from ace_metrics.plotly_dash.helpers import double_click_reset_y_range, to_fiscal_year, to_ordinal, fetch_data

dash.register_page(__name__, path="/hours-of-operations")


def generate_yearly_alert_count_df(hours_of_operation_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate alert counts by operating hours per fiscal year."""
    df = hours_of_operation_df.copy(True).set_index("month")
    df = df[["bh_day_quantities", "nights_quantities", "weekend_quantities"]]

    total = df.sum()
    total.name = "total"
    last_12_months = df.tail(12).sum()
    last_12_months.name = "last_12_months"

    df = df.assign(fiscal_year=df.index.astype(str).to_series().apply(to_fiscal_year))
    df = df.groupby("fiscal_year").sum()

    df = df.append([last_12_months, total])
    return df


layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(
                            id="hours-of-operation",
                            config=chart_config,
                            style={"height": 405},
                        ),
                    ],
                    width={"size": 12, "order": "last", "offset": 0},
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dcc.Graph(
                            id="yearly-hours-of-operation",
                            config={**chart_config, **{"doubleClick": "autosize"}},
                            style={"height": 405},
                        ),
                    ],
                    width={"size": 6, "order": "last", "offset": 0},
                ),
                dbc.Col(
                    [
                        dcc.Dropdown(
                            id="year-dropdown",
                            options=[
                                {"label": year, "value": year}
                                for year in generate_yearly_alert_count_df(
                                    fetch_data(["hours_of_operation"], True)["hours_of_operation"]
                                ).index
                            ],
                            value=["last_12_months", "total"],
                            multi=True,
                        ),
                        dcc.Graph(
                            id="yearly-alert-counts-by-operating-hours",
                            config={**chart_config, **{"doubleClick": "autosize"}},
                            style={"height": 405},
                        ),
                    ],
                    width={"size": 6, "order": "last", "offset": 0},
                ),
            ]
        ),
    ]
)


@callback(
    Output("yearly-alert-counts-by-operating-hours", "figure"),
    [Input("yearly-alert-counts-by-operating-hours", "relayoutData"), Input("theme-template-store", "data")],
    [Input("year-dropdown", "value")],
    [State("yearly-alert-counts-by-operating-hours", "figure")],
)
def update_yearly_alert_counts_by_operating_hours(
    relayoutData: Dict, template_data: Dict[str, Dict], selected_years: List[str], current_fig: Dict
) -> Union[go.Figure, Dict]:
    """Update or create chart of yearly alert counts by operating hours.

    Refresh the pie chart based on the user's year selection from the
      dropdown or the chosen legends. Update the layout and annotations
      of the chart accordingly. If no years are selected or if there's
      an attempt to update without necessary parameters, prevent the
      update to avoid errors.

    Args:
        selected_years: Years chosen by the user to display.
    """
    # If the plot already exists
    if relayoutData is not None and "hiddenlabels" in relayoutData:
        # Empty "hiddenlabels" dict means that all legends are selected
        if not relayoutData["hiddenlabels"]:
            pass
        else:
            return current_fig  # Redraw the plot with disabled legends

    # If the plot doesn't exist, create one
    if (not current_fig and relayoutData) or selected_years:
        df = generate_yearly_alert_count_df(fetch_data(["hours_of_operation"], True)["hours_of_operation"])
        df = df.rename(
            columns={
                "bh_day_quantities": "Business Hours",
                "nights_quantities": "Nights",
                "weekend_quantities": "Weekend",
            }
        )

        fig = go.Figure()
        if selected_years:
            width_per_pie = 1.0 / len(selected_years)
        else:
            return fig

        for i, year in enumerate(selected_years):
            values = df.loc[year, :]
            x_start = i * width_per_pie
            x_end = x_start + width_per_pie
            fig.add_trace(
                go.Pie(
                    labels=values.index,
                    values=values,
                    name=year,
                    textinfo="percent+value",
                    marker=dict(line=dict(color="white", width=2)),
                    textposition="inside",
                    insidetextorientation="tangential",
                    textfont=dict(size=15),
                    domain=dict(x=[x_start, x_end], y=[0, 1]),  # Set the domain for this pie chart
                )
            )
            fig.add_annotation(
                x=(x_start + x_end) / 2,
                y=-0.1,
                text=year,
                xanchor="center",
                showarrow=False,
                font=dict(size=16),
            )

        fig.update_layout(
            title="Yearly Alert Counts by Operating Hours",
            margin=dict(t=43, l=0, r=0),
            legend=dict(
                x=0,
                y=-0.1,
                traceorder="normal",
                orientation="h",
                title=dict(text=""),
            ),
            template=template_data["template"],
        )
        return fig

    raise dash.exceptions.PreventUpdate


@callback(
    Output("yearly-hours-of-operation", "figure"),
    [Input("yearly-hours-of-operation", "relayoutData"), Input("theme-template-store", "data")],
    [State("yearly-hours-of-operation", "figure")],
)
def update_yearly_hours_of_operation(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> go.Figure:
    """Update or create the yearly hours of operation bar chart.

    Generate a bar chart to represent average operation times across
      different periods, grouped by fiscal year and overall averages.
      Process, rank, and merge data before plotting. Show charts for the
      last 12 months and total averages by default.
    """
    if not current_fig and relayoutData:
        df = fetch_data(["hours_of_operation"], True)["hours_of_operation"].set_index("month")
        df = df[["bh_day_cycle_time_averages", "nights_cycle_time_averages", "weekend_cycle_time_averages"]]
        total = df.mean()
        total.name = "total"
        last_12_months = df.tail(12).mean()
        last_12_months.name = "last_12_months"

        df = df.assign(fiscal_year=df.index.astype(str).to_series().apply(to_fiscal_year))
        df = df.groupby("fiscal_year").mean()

        df = df.append([last_12_months, total]).round(1)
        df.rename(
            columns={
                "bh_day_cycle_time_averages": "Business Hours",
                "nights_cycle_time_averages": "Nights",
                "weekend_cycle_time_averages": "Weekend",
            },
            inplace=True,
        )
        df.index.name = "index"
        df = df.T

        sorted_df = pd.DataFrame()
        for year_time in df.columns:
            temp_df = df.sort_values(by=year_time, ascending=False).reset_index()
            temp_df["rank"] = temp_df.index.map(lambda x: f"{to_ordinal(x+1)}")
            temp_df = temp_df.rename(columns={"index": f"averages_{year_time}"})
            temp_df = temp_df[["rank", f"averages_{year_time}", year_time]]

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
                    text=sorted_df[f"averages_{year_time}"],
                    hoverinfo="y+text",
                )
            )
        fig.update_layout(
            title="Yearly Hours of Operation Rankings",
            xaxis_title="rank",
            yaxis_title="hours",
            margin=dict(t=43, l=0, r=0),
            template=template_data["template"],
        )
        for trace in fig.data:
            if trace.name in ["last_12_months", "total"]:
                trace.visible = True
            else:
                trace.visible = "legendonly"

        return fig

    raise dash.exceptions.PreventUpdate


@callback(
    Output("hours-of-operation", "figure"),
    [Input("hours-of-operation", "relayoutData"), Input("theme-template-store", "data")],
    [State("hours-of-operation", "figure")],
)
def update_hours_of_operation(
    relayoutData: Dict, template_data: Dict[str, Dict], current_fig: Dict
) -> Union[go.Figure, Dict]:
    """Update or create the monthly hours of operation line chart.

    Generate a line chart if it doesn't exist. If the chart already
      exists, double-clicking on it will reset the range of y-axis.
    """
    if not current_fig and relayoutData:
        df = fetch_data(["hours_of_operation"], True)["hours_of_operation"].set_index("month")
        df = df[["bh_day_cycle_time_averages", "nights_cycle_time_averages", "weekend_cycle_time_averages"]]
        fig = px.line(
            df,
            x=df.index,
            y=df.columns.tolist(),
            labels={"value": ""},
            title="Monthly Hours of Operation",
            range_x=[len(df.index) - 25, len(df.index) - 1],
            range_y=[0, df.tail(25).max().max()],
        )

        fig.update_layout(
            legend={"title_text": ""},
            yaxis_title="hours",
            margin=dict(t=43, l=0, r=0),
            template=template_data["template"],
        )
        for trace in fig.data:
            if trace.name == "bh_day_cycle_time_averages":
                trace.name = "Business Hours"
            elif trace.name == "nights_cycle_time_averages":
                trace.name = "Nights"
            else:
                trace.name = "Weekend"
            trace.mode = "lines+markers"
            trace.marker = dict(size=5, color=trace.line.color)

        return fig

    if current_fig and relayoutData == {}:
        current_fig["layout"]["yaxis"]["range"] = double_click_reset_y_range(current_fig["data"], current_fig["layout"])
        return current_fig

    raise dash.exceptions.PreventUpdate
