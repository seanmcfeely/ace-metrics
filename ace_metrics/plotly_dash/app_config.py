"""Store global configs and DataFrame."""
from .helpers import fetch_data

chart_config = {
    "scrollZoom": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": ["zoom2d", "pan2d", "lasso2d", "toggleSpikelines"],
    "modeBarButtonsToRemove": ["select2d", "resetScale2d"],
    "doubleClick": False,
}

df_store = fetch_data(
    [
        "alert_count",
        "overall_operating_alert",
        "cycle_time_sum",
        "cycle_time_mean",
        "cycle_time_std",
        "cycle_time_sum_BH",
        "cycle_time_mean_BH",
        "cycle_time_std_BH",
        "analyst_alert_quantities",
        "alert_type_quantities",
        "hours_of_operation",
    ],
    True,
)
