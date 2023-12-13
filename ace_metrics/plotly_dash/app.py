"""Entrypoint for Dash app."""

import copy
import threading
import time
from typing import List

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.io as pio
from dash import Dash, Input, Output, clientside_callback, dcc, html
from dash_bootstrap_templates import ThemeChangerAIO
from flask_login import login_required
from flask import Flask
from .database import DASH_CONFIG, get_last_update_time, initialize_database, update_database
from .helpers import change_color_brightness


class FilteredThemeChangerAIO(ThemeChangerAIO):
    """Subclass of ThemeChangerAIO to exclude specific themes."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize ThemeChangerAIO with excluded themes."""
        super().__init__(*args, **kwargs)

        offcanvas = next(child for child in self.children if "Offcanvas" in str(type(child)))
        radio_items = next(child for child in offcanvas.children if "RadioItems" in str(type(child)))

        # Filter out ugly themes
        not_allowed_themes = ["MORPH", "QUARTZ", "SLATE", "CYBORG"]
        radio_items.options = [option for option in radio_items.options if option["label"] not in not_allowed_themes]


filtered_theme_changer = FilteredThemeChangerAIO(
    aio_id="theme-changer",
    button_props={
        "color": "danger",
        "children": "Change theme",
    },
    radio_props={"persistence": True},
)

chart_config = {
    "scrollZoom": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": ["zoom2d", "pan2d", "lasso2d", "toggleSpikelines"],
    "modeBarButtonsToRemove": ["select2d", "resetScale2d"],
    "doubleClick": False,
}


def threaded_db_update() -> None:
    """Run a thread indefinitely that updates the local database.

    Fetch tables from ACE database and update the global DataFrame
      `df_store` and the `last_update_time` variable every 5 minutes.
    """
    while True:
        update_database()
        time.sleep(300)


def generate_main_content() -> dash.page_container:
    """Generate the main content for the Dash application.

    Returns:
        The container for Dash application pages.
    """
    return dash.page_container


def serve_layout() -> dbc.Container:
    """Create the layout of the webapp using Dash Bootstrap Components.

    Define the sidebar and main content area, with the sidebar including
      navigation links, a graph hotkeys accordion, and a theme switcher.

    Returns:
        A Dash Bootstrap container for the full layout of the webapp.
    """
    sidebar = dbc.Col(
        [
            html.H2("ACE Metrics Dashboard", className="display-7"),
            html.Hr(),
            dbc.Nav(
                [
                    dbc.Card(
                        dbc.CardBody(
                            [
                                dbc.NavLink("Alerts", href="/", active="exact", id="alerts-nav"),
                                dbc.NavLink(
                                    "Hours of Operations", href="/hours-of-operations", id="hours-of-operations-nav"
                                ),
                                dbc.NavLink("Events", href="/events", id="events-nav"),
                            ]
                        )
                    ),
                    dbc.Accordion(
                        [
                            dbc.AccordionItem(
                                [
                                    html.P("Z: Pan/Zoom"),
                                    html.P("X: Autoscale X and Y"),
                                    html.P("Double-click: Autoscale Y"),
                                ],
                                title="Graph Hotkeys",
                            ),
                        ],
                        start_collapsed=True,
                    ),
                    html.Span(
                        [
                            html.Div(
                                [
                                    dbc.Label(className="fa fa-moon", html_for="switch"),
                                    dbc.Switch(
                                        id="color-mode-switch",
                                        value=True,
                                        className="d-inline-block ms-1",
                                        persistence=True,
                                    ),
                                    dbc.Label(className="fa fa-sun", html_for="switch"),
                                ],
                                style={"marginBottom": "8px"},
                            ),
                            filtered_theme_changer,
                            dcc.Store(id="theme-template-store"),
                            html.Div(
                                [
                                    html.P(
                                        f"Last updated: {get_last_update_time()}",
                                        style={"marginTop": "15px"},
                                    ),
                                ]
                            ),
                        ],
                        className="d-flex flex-column px-3 pt-4",  # Stack vertically and center align
                    ),
                ],
                vertical=True,
                pills=True,
            ),
        ],
        width={"size": 2, "order": "first", "offset": 0},
        style={
            "position": "sticky",
            "top": 0,
            "height": "100vh",
            "overflowY": "auto",
        },
        className="pt-2",
    )
    return dbc.Container(
        [
            dbc.Row(
                [
                    sidebar,
                    dbc.Col(
                        html.Div([generate_main_content()], id="main-content-div"),
                        style={"maxWidth": "none"},
                        width={"size": 10, "order": "last", "offset": 0},
                    ),
                ],
                className="pt-5",
            ),
            dcc.Store(id="css-store"),
            html.Script(id="css-script"),
        ],
        fluid=True,
    )


def create_dash_app(flask_server: Flask = None) -> Dash:
    """Create and return dash app object."""
    initialize_database()
    if flask_server:
        dash_app = Dash(
            server=flask_server,
            name="Dashboard",
            pages_folder=DASH_CONFIG["pages_folder_dir"],
            assets_folder=DASH_CONFIG["assets_folder_dir"],
            requests_pathname_prefix=DASH_CONFIG["requests_pathname_prefix"],
            routes_pathname_prefix=DASH_CONFIG["routes_pathname_prefix"],
            use_pages=True,
            external_stylesheets=[dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
        )

        # Protected routes
        for view_function in dash_app.server.view_functions:
            if view_function.startswith(dash_app.config.routes_pathname_prefix):
                dash_app.server.view_functions[view_function] = login_required(
                    dash_app.server.view_functions[view_function]
                )
    else:
        dash_app = Dash(
            __name__,
            use_pages=True,
            external_stylesheets=[dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=False,
        )
    dash_app.layout = serve_layout

    # Callback to update main content based on theme
    @dash_app.callback(
        [Output("main-content-div", "children"), Output("css-store", "data"), Output("theme-template-store", "data")],
        [
            [Input(filtered_theme_changer.ids.radio("theme-changer"), "value")],
            [Input("color-mode-switch", "value")],
        ],
    )
    def update_main_content_with_theme(selected_theme: List[str], color_mode: List[bool]) -> tuple:
        """Update plot template and CSS for chosen theme and color mode.

        There should be only one element in both parameters.

        Args:
            selected_theme: The theme to apply.
            color_mode: True for light mode, False for dark mode.

        Returns:
            The updated main content and CSS data as a tuple.
        """
        # Extract the theme name from the selected theme path
        theme_name = selected_theme[0].split("/")[-2]
        theme_name = "bootstrap" if theme_name == "css" else theme_name
        # Append '_dark' to the theme name if the color mode is dark
        if not color_mode[0]:
            theme_name += "_dark"
        # Customize the plotly template based on the selected theme
        template_copy = copy.deepcopy(pio.templates[theme_name])
        darker_background = change_color_brightness(
            template_copy["layout"]["plot_bgcolor"], 0.85
        )  # For better contrast
        template_copy["layout"]["plot_bgcolor"] = darker_background
        template_copy["layout"]["colorway"] = (
            px.colors.qualitative.Light24 if "dark" in theme_name else px.colors.qualitative.Dark24
        )

        css_string = f""".Select-menu-outer {{ background-color: {darker_background} !important; }}"""
        return (generate_main_content(), {"css": css_string}, {"template": template_copy})

    # Clientside callback to update theme color scheme
    clientside_callback(
        """
        (switchOn) => {
        switchOn
            ? document.documentElement.setAttribute('data-bs-theme', 'light')
            : document.documentElement.setAttribute('data-bs-theme', 'dark')
        return window.dash_clientside.no_update
        }
        """,
        Output("color-mode-switch", "id"),
        Input("color-mode-switch", "value"),
    )
    # Clientside callback to add custom css
    clientside_callback(
        """
        function(cssData) {
            if (cssData) {
                var styleTag = document.getElementById('custom-style');
                if (!styleTag) {
                    styleTag = document.head.appendChild(document.createElement('style'));
                    styleTag.id = 'custom-style';
                }
                styleTag.innerHTML = cssData.css;
                return;
            }
        }
        """,
        Output("css-script", "children"),
        Input("css-store", "data"),
    )
    return dash_app


if __name__ == "__main__":
    threading.Thread(target=threaded_db_update, daemon=True).start()
    create_dash_app().run(debug=False, port=5432, threaded=False)
