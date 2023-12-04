"""Operations for local SQLite database to store all metrics."""

import logging
import os
import sqlite3
import sys
import warnings
from datetime import datetime, timedelta
from typing import Any, Dict

import sqlite_utils
from dateutil.relativedelta import relativedelta

from ace_metrics.alerts import (
    VALID_ALERT_STATS,
    define_business_time,
    generate_hours_of_operation_summary_table,
    generate_overall_summary_table,
    get_alerts_between_dates,
    statistics_by_month_by_dispo,
)

from ..alerts.alert_types import alert_type_quantities_by_category_by_month
from ..alerts.users import alert_quantities_by_user_by_month
from ..config import DEFAULT_CONFIG_PATHS, load_config
from ..helpers import connect_to_database
from .data_exceptions import apply_alert_data_exceptions

logging.basicConfig(level=logging.INFO)
warnings.filterwarnings(action="ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy connectable.*")

DEFAULT_DATA_DIR = os.path.join("/", "opt", "ace", "data", "stats", "metrics")
config = load_config(DEFAULT_CONFIG_PATHS)
if not config:
    logging.error("You must define and supply a configuration. See `ace-metrics -h | grep config`")
    sys.exit(1)
try:
    DATABASE_CONFIG = config["database_default"]
    DASH_CONFIG = config["plotly_dash"]
except KeyError:
    logging.error("database_default and plotly_dash sections need to be defined in the configuration file.")
    sys.exit(1)

if not DASH_CONFIG.get("enabled", None) or not DASH_CONFIG.getboolean("enabled"):
    logging.warning("Dash is not enabled. Exiting...")
    sys.exit(1)

DATA_DIR = DATABASE_CONFIG.get("data_dir", DEFAULT_DATA_DIR) or DEFAULT_DATA_DIR


def floor_datetime_month(dt):
    """Floor a datetime to the absolute beginning of the month."""
    return dt - timedelta(days=dt.day - 1, hours=dt.hour, minutes=dt.minute, seconds=dt.second)


def get_alert_tables_by_month(months_ago: int) -> Dict[str, Any]:
    """Retrieve alert tables grouped by month.

    Args:
        months_ago: Number of months before the current date to
          calculate the start date for alert data retrieval.

    Returns:
        A dictionary mapping table names to their respective alert data
          aggregated by month.
    """
    end_date = datetime.now()
    start_date = floor_datetime_month(end_date - relativedelta(months=months_ago))
    db = connect_to_database(DATABASE_CONFIG)
    business_hours = define_business_time()
    logging.info(f"Querying alerts data from {start_date} up until {end_date} (now).")

    alerts = get_alerts_between_dates(start_date, end_date, db, selected_companies=["ashland"])
    exception_list = DATABASE_CONFIG["alert_data_exception_list"].split(",")
    alerts = apply_alert_data_exceptions(config, alerts, exception_list)
    alert_stat_map = statistics_by_month_by_dispo(alerts)
    alert_stat_map_bh = statistics_by_month_by_dispo(alerts, business_hours=business_hours)
    for stat in VALID_ALERT_STATS:
        if "time" in stat:
            alert_stat_map_bh[f"{stat}_BH"] = alert_stat_map_bh.pop(f"{stat}")
    database_table_map = alert_stat_map | alert_stat_map_bh

    database_table_map["analyst_alert_quantities"] = alert_quantities_by_user_by_month(start_date, end_date, db)

    alert_type_categories_key = {}
    for k, v in config["alert_type_categories_key"].items():
        alert_type_categories_key[k] = v.split(",")
    database_table_map["alert_type_quantities"] = alert_type_quantities_by_category_by_month(
        start_date, end_date, db, alert_type_categories_key
    )

    database_table_map["hours_of_operation"] = generate_hours_of_operation_summary_table(
        alerts.copy(), business_hours, True
    )
    database_table_map["overall_operating_alert"] = generate_overall_summary_table(alerts.copy(), business_hours, True)
    return database_table_map


def initialize_database() -> bool:
    """Initialize or reuse a local SQLite database."""
    database_path = f"{DATA_DIR}/ace_metrics_database.sqlite"
    if os.path.isfile(database_path):
        logging.info(f"A database already exists at {database_path}. Proceeding using this database...")
        return True
    logging.info(f"Database does not exist. Creating a new one at {database_path}...")
    database_table_map = get_alert_tables_by_month(DATABASE_CONFIG.getint("alert_data_scope_months_ago", fallback=60))

    with sqlite3.connect(f"{DATA_DIR}/ace_metrics_database.sqlite") as conn:
        for table_name, df in database_table_map.items():
            logging.info(f"Inserting {table_name} table into sqlite database...")
            df.to_sql(table_name, conn, if_exists="replace", index=True, dtype={"month": "TEXT PRIMARY KEY"})

    # Make a copy of the initialized database
    with open(f"{DATA_DIR}/ace_metrics_database.sqlite", "rb") as f1:
        with open(f"{DATA_DIR}/ace_metrics_database_init.sqlite", "wb") as f2:
            f2.write(f1.read())
    return True


def update_database() -> str:
    """Upsert the local database with alert data from the past month.

    Returns:
        A timestamp string when the update was completed.
    """
    logging.info("Updating database...")
    update_table_map = get_alert_tables_by_month(1)

    with sqlite3.connect(f"{DATA_DIR}/ace_metrics_database.sqlite") as conn:
        db = sqlite_utils.Database(conn)
        for table in update_table_map:
            db[table].upsert_all(update_table_map[table].reset_index().to_dict(orient="records"), pk="month")

    logging.info("Database update completed.")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
