"""Settings page for Dash app."""

from typing import Dict, List, Union

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html, callback_context
from plotly.subplots import make_subplots
from datetime import date, datetime

from flask import session

from ace_metrics.plotly_dash.app import chart_config
from ace_metrics.plotly_dash.helpers import fetch_data, VALID_TABLE_NAMES_MAP
from ace_metrics.helpers import dataframes_to_xlsx_bytes
from ace_metrics.plotly_dash.database import DASH_CONFIG

dash.register_page(__name__, path="/settings")


def serve_layout() -> dbc.Container:
    """Dynamically create layout based on user permission."""
    advanced_user_ids = DASH_CONFIG.get("advanced_user_ids", None)
    if advanced_user_ids and session.get("user_id", None) in [i.strip() for i in advanced_user_ids.split(",")]:
        return dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.P("Download metrics data:"),
                                html.Div(
                                    [
                                        dcc.DatePickerRange(
                                            id="date-picker",
                                            min_date_allowed=date(2017, 9, 9),
                                            end_date=datetime.now().strftime("%Y-%m-%d"),
                                            clearable=True,
                                            reopen_calendar_on_clear=True,
                                            style={
                                                "display": "inline-block",
                                                "marginRight": "10px",
                                            },
                                        ),
                                        dbc.Button("Download", id="btn-download", color="primary"),
                                    ],
                                    style={"marginLeft": "10px"},
                                ),
                                dcc.Download(id="download-data"),
                            ],
                            width=6,
                        )
                    ]
                )
            ]
        )
    else:
        return html.Div(
            [
                html.H1("Access Denied"),
                html.P("You do not have permission to view this page."),
            ]
        )


layout = serve_layout


@callback(
    Output("download-data", "data"),
    Input("btn-download", "n_clicks"),
    Input("date-picker", "start_date"),
    Input("date-picker", "end_date"),
    prevent_initial_call=True,
)
def download_data(n_clicks, start_date, end_date):
    """Download metrics data as Excel file for selected date range."""
    ctx = callback_context

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    # Check if the callback was triggered by the button click
    if trigger_id == "btn-download" and start_date and end_date and start_date < end_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m")
        end_date = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m")
        df_map = fetch_data(VALID_TABLE_NAMES_MAP.keys(), True)
        for table_name, df in df_map.items():
            df.set_index("month", inplace=True)
            if table_name == "alert_count":
                df["delivery_combined"] = df["weaponization"] + df["delivery"] + df["reconnaissance"]
            df_map[table_name] = df[(df.index >= start_date) & (df.index <= end_date)]
            df_map[table_name].name = df.name
        filebytes = dataframes_to_xlsx_bytes(df_map.values())
        return dcc.send_bytes(filebytes, f"ACE_Metrics_{int(datetime.timestamp(datetime.now()))}.xlsx")
    else:
        # Callback was not triggered by the button click, do nothing
        return dash.no_update
