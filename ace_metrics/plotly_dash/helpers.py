"""Utility functions for database operations and plotting."""

import sqlite3
from typing import Dict, List, Tuple, Union

import pandas as pd

from .database import DATA_DIR

VALID_TABLE_NAMES = [
    "analyst_alert_quantities",
    "alert_type_quantities",
    "hours_of_operation",
    "overall_operating_alert",
    "cycle_time_sum",
    "cycle_time_mean",
    "cycle_time_min",
    "cycle_time_max",
    "cycle_time_std",
    "alert_count",
    "cycle_time_sum_BH",
    "cycle_time_mean_BH",
    "cycle_time_min_BH",
    "cycle_time_max_BH",
    "cycle_time_std_BH",
]


def fetch_data(tables: List[str], clean_column_names: bool = False) -> Dict[str, pd.DataFrame]:
    """Fetch tables from SQLite database.

    Args:
        tables: A list of table names to fetch data from.
        clean_column_names: Flag to clean column names (rename 'index'
          to 'month' and lowercase all column names).

    Returns:
        A dictionary where keys are table names and values are
          DataFrames with the fetched data.

    Raises:
        ValueError: If any of the table names provided are not valid.
    """
    conn = sqlite3.connect(f"{DATA_DIR}/ace_metrics_database.sqlite")
    df_dict = {}
    for table in tables:
        if table not in VALID_TABLE_NAMES:
            raise ValueError("Invalid table name")
        df = pd.read_sql_query(f"SELECT * FROM {table};", conn)
        if clean_column_names:
            df.rename(columns={"index": "month"}, inplace=True)
            df.columns = df.columns.str.lower()
        df_dict[f"{table}"] = df
    conn.close()
    return df_dict


def to_ordinal(n: int) -> str:
    """Convert an integer to its ordinal representation as a string."""
    suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    return str(n) + suffix


def to_fiscal_year(year_month_str: str) -> str:
    """Convert a `YYYYMM` string to its corresponding fiscal year."""
    year = int(year_month_str[:4])
    month = int(year_month_str[4:])
    if month >= 10:
        year += 1
    return str(year)


def double_click_reset_y_range(
    fig_data: List[Dict], fig_layout: Dict, side_by_side_plot: bool = False
) -> Union[Tuple[float, float], List[Tuple[float, float]]]:
    """Reset the y-range when double-clicking plot area.

    Args:
        fig_data: A list of dicts, each representing a trace of data.
        fig_layout: A dict with the layout configuration of the figure.
        side_by_side_plot: Indicates if the plot is a side-by-side plot.

    Returns:
        A tuple containing the new y-axis range for the plot. If the
          plot is side by side, returns a list of tuples with the range
          for each plot.
    """
    x_axis = fig_data[0]["x"]
    cur_xrange = fig_layout["xaxis"]["range"]
    y1_min, y1_max = float("inf"), float("-inf")
    if side_by_side_plot:
        cur_xrange2 = fig_layout["xaxis2"]["range"]
        y2_min, y2_max = float("inf"), float("-inf")
    # Loop through all traces to find the min and max y-values within
    # the current x-axis range of each subplot
    for trace in fig_data:
        if trace.get("visible") == "legendonly":
            continue  # Skip this trace if it's not visible

        x_values, y_values = trace["x"], trace["y"]

        for x, y in zip(x_values, y_values):
            # Since both subplots share the legends from the first plot,
            # the second subplot will have showlegend=False.
            if "showlegend" not in trace or trace.get("showlegend") is True:
                if (
                    x_axis[max(0, int(-(-cur_xrange[0] // 1)))]
                    <= x
                    <= x_axis[min(int(cur_xrange[1] // 1), len(x_axis) - 1)]
                ):
                    y1_min = min(y1_min, y)
                    y1_max = max(y1_max, y)
            elif side_by_side_plot:
                if (
                    x_axis[max(0, int(-(-cur_xrange2[0] // 1)))]
                    <= x
                    <= x_axis[min(int(cur_xrange2[1] // 1), len(x_axis) - 1)]
                ):
                    y2_min = min(y2_min, y)
                    y2_max = max(y2_max, y)
    if side_by_side_plot:
        return [(y1_min, y1_max), (y2_min, y2_max)]
    return (y1_min, y1_max)


def change_color_brightness(hex_color: str, factor: float) -> str:
    """Change the brightness of a color represented in hex format."""
    hex_color = hex_color.lstrip("#")

    if len(hex_color) == 3:
        hex_color = "".join([x * 2 for x in hex_color])
    elif len(hex_color) != 6:
        raise ValueError("Input hex color should be 3 or 6 characters long after removing '#'")

    try:
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        raise ValueError("Invalid hex color")

    # Darken the color by the given factor
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)

    # Ensure that the values are within the 0-255 range
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    # Convert the RGB color back to hex
    darker_hex_color = "#{:02x}{:02x}{:02x}".format(r, g, b)

    return darker_hex_color
