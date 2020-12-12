"""Functions that are helpful to other metric funcitons."""

import io
import os
import logging
import pymysql
import tarfile
import configparser

import pandas as pd
from datetime import timedelta, datetime, time
from dateutil.relativedelta import relativedelta

from typing import Mapping, List, Tuple

from .alerts import FRIENDLY_STAT_NAME_MAP

CompanyID = int
CompanyName = str
CompanyMap = Mapping[CompanyID, CompanyName]

def generate_html_plot(data_table: pd.DataFrame,
                       kind="line",
                       legend="top_left",
                       toolbar_location="above",
                       xlabel="Month",
                       figsize=(1000,600),
                       title=None,
                       ylabel=None) -> str:
    """Convert a datatable into an HTML Bokeh plot.

    This is very customized with defaults.

    Plot kinds from pandas_bokeh:
    https://github.com/PatrikHlobil/Pandas-Bokeh/blob/1a8309ca7b5cbee527cf951668e4f8a1250cecb3/pandas_bokeh/plot.py#L167

    Args:
        data_table: A pandas DataFrame

    Returns:
        An HTML element representing the plot,
        as a string.
    """
    import math
    import pandas_bokeh

    if ylabel is None:
        ylabel="Hours"

    if title is None:
        try:
            title = data_table.name
        except AttributeError:
            title = ""    

    p = data_table.plot_bokeh(kind=kind,
                              show_figure=False,
                              legend=legend,
                              toolbar_location=toolbar_location,
                              figsize=figsize,
                              title=title,
                              zooming=False,
                              xlabel=xlabel,
                              ylabel=ylabel)

    # override legend defaults
    p.legend.background_fill_alpha = 0
    p.legend.border_line_alpha = 0
    p.xaxis.major_label_orientation = math.pi/4
    if ylabel is not None and 'alert' in title.lower():
        p.yaxis.axis_label = "Number of Alerts"
    return pandas_bokeh.embedded_html(p)

def get_companies(con: pymysql.connections.Connection) -> CompanyMap:
    """Query the database for all companies.

    Args:
        con: a pymysql database connectable

    Returns:
        A dict of companies like so:
          {company_id: 'company_name'}, ..
    """

    companies = {}
    cursor = con.cursor()
    cursor.execute("select * from company")
    for c_id,c_name in cursor.fetchall():
        companies[c_id] = c_name
    return companies

def apply_company_selection_to_query(query: str, company_ids: list, selected_companies: list) -> str:
    """Update a metric SQL query to select where companies.

    Args:
        query: An ACE DB query structered for reduction by company ID.
          Such a query should have two "{}" back to back, like: {}{}
        company_ids: list of all valid company IDs
        selected_companies: A list of companies to select alerts for, by name.
          If the list is empty, all alerts are selected.

    Returns:
        An updated SQL query string.

    """
    return query.format(' AND ' if company_ids else '', '( ' + ' OR '.join(['company.name=%s' for company in selected_companies]) +') ' if company_ids else '')

def sanitize_table_name(table_name=None, keep_friendly=False) -> str:
    """Sanitize a table name.

    Try to make a table name safe to be a file name.

    Args:
        table_name: The table name to sanitize.
        keep_friendly: Do not map detailed friendly statistic names back
          to their less descriptive key names.

    Returns:
       A santized name string.
    """

    if table_name is None:
        return f"No name - {datetime.now().timestamp()}"

    safe_name = table_name.strip()

    if not keep_friendly:
        # map the friendly names back to key name
        for stat_key,stat_name in FRIENDLY_STAT_NAME_MAP.items():
            if stat_name in safe_name:
                safe_name = safe_name.replace(stat_name, stat_key)

    _invalid_chars = ["\\", "*", "?", ":", "/", "[", "]"]
    for invalid_char in _invalid_chars:
        safe_name = safe_name.replace(invalid_char, '-')

    return safe_name

def dataframes_to_archive_bytes_of_json_files(tables: List[pd.DataFrame]) -> bytes:
    """Create byte archive of tables as json files.

    Convert each table to its json file bytestring. Put each bytestring
    into a tar archive and return the tar.gz bytes of that archive.
    Write to a file or send wherever.

    Args:
        tables: A list of pd.DataFrames

    Returns:
        The bytestring of a tar.gz archive containing the
        tables as json files.
    """

    buf = io.BytesIO()
    tar = tarfile.open(mode="w:gz", fileobj=buf)
    for table in tables:
        if not table.name:
            safe_table_name = sanitize_table_name()
        else:
            safe_table_name = sanitize_table_name(table.name, keep_friendly=True)

        table_buf = io.BytesIO()
        table_bytes = table.to_json().encode('utf-8')
        table_info = tarfile.TarInfo(name=f"{safe_table_name}.json")
        table_info.size = len(table_bytes)
        table_buf.write(table_bytes)
        table_buf.seek(0)
        tar.addfile(table_info, table_buf)
        table_buf.close()

    tar.close()
    buf.seek(0)
    filebytes = buf.read()
    buf.close()
    return filebytes

def dataframes_to_xlsx_bytes(tables: List[pd.DataFrame]) -> bytes:
    """Export dataframes to xlsx bytes.

    Write the bytes to a file or send them wherever.

    Args:
        tables: A list of pd.DataFrames

    Returns:
        The bytestring representation of the xlsx file.
    """

    tab_names = []
    tab_name_map = {}
    table_tab_map = {}
    # sanitize and make tab name map
    for table in tables:
        if table.name:
            table_name = table.name
        else:
            logging.warning("metric table has no name.")
            table_name = sanitize_table_name()
        clean_table_name = sanitize_table_name(table.name)

        # do additional table name cleanup for excel
        # try to clean up alert_type names
        name_parts = clean_table_name.split(' - ')
        if name_parts:
            _tmp_name = ""
            for part in name_parts[:-1]:
                _tmp_name += f"{part[0].upper()}-"
            clean_table_name = f"{_tmp_name}{name_parts[-1]}"

        # openpyxl guidance to keep names to 31 chars or less
        if len(clean_table_name) > 31:
            clean_table_name = clean_table_name[:31]

        if clean_table_name in tab_names:
            logging.warning(f"name collision for {clean_table_name}")
            # 30 char collision name
            clean_table_name = f"Collision - {datetime.now().timestamp()}"

        tab_names.append(clean_table_name)

        logging.info(f"changed table name from '{table_name}' to '{clean_table_name}'")
        # will add this helpful info to the excel sheet
        tab_name_map[clean_table_name] = table_name
        table_tab_map[clean_table_name] = table

    xlsx_bytes = io.BytesIO()
    writer = pd.ExcelWriter(xlsx_bytes)
    # write the tab name map first
    tab_name_map_df = pd.DataFrame.from_dict(tab_name_map,
                                            orient='index',
                                            columns=['ACE Data Table Name'])
    tab_name_map_df.index.names = ['Tab Name']
    tab_name_map_df.to_excel(writer, "Tab Name Map")

    # write the tables to excel tabs
    for name, table in table_tab_map.items():
        try:
            table.to_excel(writer, name)
        except Exception as e:
            logging.error(f"failed to write table: {e}")

    writer.close()
    xlsx_bytes.seek(0)
    filebytes = xlsx_bytes.read()
    xlsx_bytes.close()

    return filebytes

def connect_to_database(config: configparser.SectionProxy) -> pymysql.connections.Connection:
    """Connect to a configured ACE DB.

    Args:
        config: A configparser section that defines
          the database connection.

    Returns:
        pymysql.connections.Connection to an ACE DB
    """
    from getpass import getpass

    ssl_settings = None
    if os.path.exists(config.get('ssl_ca_path')):
        ssl_settings = {'ca': config['ssl_ca_path']}

    password = config.get('pass')
    if not password:
        password = getpass(f"Enter password for {config['user']}@{config['host']}: ")

    db = pymysql.connect(host=config['host'], user=config['user'], password=password, database=config['database'], ssl=ssl_settings)
    return db


def get_month_keys_between_two_dates(start_date: datetime, end_date: datetime) -> list:
    """Get unique %Y%m (Months) between dates."""

    months = []
    while start_date.year <= end_date.year:
        while start_date.month <= end_date.month:
            months.append(datetime.strftime(start_date, '%Y%m'))
            start_date += relativedelta(months=1)
            break

    return months
