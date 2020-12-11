"""Metric functions for working with users and alerts.
"""

import os
import logging

import pymysql
import businesstime
import pandas as pd

from typing import Dict, Mapping
from datetime import datetime

from ..helpers import get_month_keys_between_two_dates
from . import statistics_by_month_by_dispo, VALID_ALERT_STATS, FRIENDLY_STAT_NAME_MAP, ALERTS_BY_MONTH_AND_USER_QUERY

UserMap = Mapping[int, Dict[str, str]]
UserStatMap = Mapping[str, Mapping[str, pd.DataFrame]]

def get_all_users(con: pymysql.connections.Connection) -> UserMap:
    """Get all ACE users.

    Args:
        con: a pymysql database connectable

    Returns:
        A dictionary where the key is the user ID integer and the
        value is a dictionary like:
            {'username': username,
             'display_name': display_name,
             'queue': queue
             }
    """
    cursor = con.cursor()
    # NOTE: come back and add `enabled` once the column exists
    cursor.execute("SELECT id,username,display_name,queue FROM users")
    users = {}
    for user_id, username, display_name, queue in cursor.fetchall():
        users[user_id] = {'username': username,
                          'display_name': display_name,
                          'queue': queue}
    return users

def generate_user_alert_stats(alerts: pd.DataFrame, users: UserMap, business_hours=False) -> UserStatMap:
    """Generate alert statistics for all users.

    Given a dataframe of alerts, categorize the alerts by the user that
    dispositioned the alerts, and generated alert statistics for each user.

    Args:
        alert: A pd.DataFrame of alerts
        users: A dictionary mapping user IDs to user attributes
        business_hours: A boolean that if True, will calulate time base
          statistics with business hours applied.

    Returns:
        A dictionary where the keys are usernames and the values are alert
        statatistic maps for users.
    """

    all_user_alert_stats = {}
    for user_id in users.keys():
        username = users[user_id]['username']
        display_name = users[user_id].get('display_name', None)
        user_alerts = alerts[alerts.disposition_user_id == user_id]
        user_alert_stats = statistics_by_month_by_dispo(user_alerts, business_hours=business_hours)
        for stat in VALID_ALERT_STATS:
            if display_name:
                user_alert_stats[stat].name = f"{display_name}: {FRIENDLY_STAT_NAME_MAP[stat]}"
            else:
                user_alert_stats[stat].name = f"{username}: {FRIENDLY_STAT_NAME_MAP[stat]}"
        all_user_alert_stats[user_id] = user_alert_stats

    return all_user_alert_stats

def alert_quantities_by_user_by_month(start_date: datetime,
                                      end_date: datetime,
                                      con: pymysql.connections.Connection,
                                      query: str =ALERTS_BY_MONTH_AND_USER_QUERY,
                                      exclude_analysts_without_data=True) -> pd.DataFrame:
    """Get Alert quantities by user and month."""

    months = get_month_keys_between_two_dates(start_date, end_date)
    users = get_all_users(con)

    cursor = con.cursor()

    data = {}
    for uid, udata in users.items():
        month_data = {}
        for month in months:
            cursor.execute(query, (month, udata['username']))
            stats = cursor.fetchone()
            if stats:
                month_data[month] = stats[0]
        if month_data and exclude_analysts_without_data:
            # don't record users that have no data
            data[udata['username']] = month_data

    user_dispositions_per_month = pd.DataFrame(data=data)
    user_dispositions_per_month.name = "Alert Quantities by Analyst"
    user_dispositions_per_month.fillna(value=0,inplace=True)
    return user_dispositions_per_month
