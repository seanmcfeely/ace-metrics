import os
import sys
import json
import logging
import configparser
import datetime
import pymysql
import argparse
import argcomplete

import pandas as pd

from tabulate import tabulate

from .alerts import ( VALID_ALERT_STATS, 
                      FRIENDLY_STAT_NAME_MAP,
                      ALERTS_BY_MONTH_DB_QUERY,
                      statistics_by_month_by_dispo )


STDOUT_FORMATS = ['json', 'csv', 'ascii_table', 'print']

FILEOUT_FORMATS = ['json', 'xlsx']#, 'csv', 'sqlite']

def stdout_like(df: pd.DataFrame, format='print'):
    if format not in STDOUT_FORMATS:
        logging.warning(f"{format} is not a supported output format for the cli")
        return False

    table_name = ""
    try:
        table_name = f"{df.name}:"
    except AttributeError:
        # table has no name
        pass

    if format == 'json':
        print(df.to_json())
        return

    if format == 'csv':
        print(df.to_csv())
        return

    if format == 'ascii_table':
        print()
        print(table_name)
        print(tabulate(df, headers='keys', tablefmt='simple'))
        print()
        return
    
    print()
    print(table_name)
    print(df)
    print()
    return

def build_metric_user_parser(user_parser: argparse.ArgumentParser) -> None:
    """Given an argparse subparser, build a metric user parser.

    Args:
        user_parser: An argparse.ArgumentParser.

    Returns: None
    """

    user_parser.add_argument('-l', '--list-users', action='store_true',
                              help='List all users')
    user_parser.add_argument('-u', '--user', action='append', dest='users', default=[],
                             help='A list of users to generate statistics for. Default: All users.')
    user_parser.add_argument('-tac', '--total-alert-count-breakdown',
                             action='store_true', help="Total count of Alerts worked by analyst by month.")

    for stat in VALID_ALERT_STATS:
        user_parser.add_argument(f'--{stat}', action='store_true', dest=f"user_stat_{stat}",
                                 help=FRIENDLY_STAT_NAME_MAP[stat])
    user_parser.add_argument('--all-stats', dest='all_user_stats', action='store_true',
                             help="Return all of the available statistics.")

def build_metric_alert_type_parser(alert_type_parser: argparse.ArgumentParser) -> None:
    """Given an argparse subparser, build a metric alert type parser.

    Args:
        alert_type_parser: An argparse.ArgumentParser.

    Returns: None
    """

    alert_type_parser.add_argument('-l', '--list-alert-types', action='store_true',
                              help='List the types of alerts')
    alert_type_parser.add_argument('-t', '--type', action='append', dest='types', default=[],
                             help='A list of alert_types to generate statistics for. Default: All alert types.')
    alert_type_parser.add_argument('-c', '--overall-count-breakdown', action='store_true',
                             help='An overall breakdown of alert counts by alert type.')

    for stat in VALID_ALERT_STATS:
        alert_type_parser.add_argument(f'--{stat}', action='store_true', dest=f"alert_type_stat_{stat}",
                                       help=FRIENDLY_STAT_NAME_MAP[stat])
    alert_type_parser.add_argument('--all-stats', dest='all_at_stats', action='store_true',
                                   help="Return all of the available statistics.")

def build_metric_alert_parser(alert_parser: argparse.ArgumentParser) -> None:
    """Given an argparse subparser, build a metric alert parser.

    Build an alert parser that defines how to interface with the
    ACE metrics library for ACE alert data.
    
    Args:
        alert_parser: An argparse.ArgumentParser.

    Returns: None
    """

    alert_parser.add_argument('-hop', '--hours-of-operation', action='store_true',
                              help='Generate "Hours of Operation" summary by month')
    alert_parser.add_argument('-avg-ct-sum', '--average-alert-cycletime-summary', action='store_true',
                              help="Overall summary of alert cycle times by month" )

    for stat in VALID_ALERT_STATS:
        alert_parser.add_argument(f'--{stat}', action='store_true', dest=f"alert_stat_{stat}",
                                  help=FRIENDLY_STAT_NAME_MAP[stat])
    alert_parser.add_argument('--all-stats', dest='all_alert_stats', action='store_true',
                              help="Return all of the available statistics.")

    alert_subparsers = alert_parser.add_subparsers(dest='alert_metric_target')

    user_parser = alert_subparsers.add_parser("users", help="user based alert metrics")
    build_metric_user_parser(user_parser)

    alert_type_parser = alert_subparsers.add_parser("types", help="alert metrics by alert types")
    build_metric_alert_type_parser(alert_type_parser)

def build_metric_event_parser(event_parser: argparse.ArgumentParser) -> None:
    """Given an argparse subparser, build a metric event parser.

    Build an event parser that defines how to interface with the
    ACE metrics library for ACE event data.
    
    Args:
        event_parser: An argparse.ArgumentParser.

    Returns: None
    """ 

    event_parser.add_argument('-i', '--incidents', action='store_true',
                              help='Create incident table from event table')
    event_parser.add_argument('-io', '--incidents-only', action='store_true',
                              help='Only return incidents table (skip event table)')
    event_parser.add_argument('-ce', '--count-emails', action='store_true',
                              help='Count emails, in each event, per company.')

def build_metric_parser(parser: argparse.ArgumentParser) -> None:
    """Build the ACE metric parser.
    
    Args:
        parser: An argparse.ArgumentParser.

    Returns: None
    """

    # Default date range will be the last 7 days.
    default_start_datetime = (datetime.datetime.today() - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    default_end_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    parser.add_argument('-so', '--stdout-format', default='print', action='store', choices=STDOUT_FORMATS,
                        help="desired standard output format. ~~~ NOTE: 'print' (the default) will also summarize large tables. Use 'ascii_table' to avoide that.")
    parser.add_argument('-fo', '--fileout-format', default=None, action='store', choices=FILEOUT_FORMATS,
                        help="desired file output format. Default is xls.")
    parser.add_argument('-f', '--filename', action='store', default=None, help="The name of a file to write results to.")
    parser.add_argument('-c', '--company', action='append', dest='companies', default=[],
                        help="A list of company names to gather metrics for. Default is all defined companies.")
    parser.add_argument('-bh', '--business-hours', action='store', default=False,
                        help="Use business hours for all time based stats. Set like start_hour,end_hour,time_zone. Example: 6,18,US/Eastern")
    parser.add_argument('-s', '--start_datetime', action='store', default=default_start_datetime,
                        help="The start datetime data is in scope. Format: YYYY-MM-DD HH:MM:SS. Default: 7 days ago.")
    parser.add_argument('-e', '--end_datetime', action='store', default=default_end_datetime,
                         help="The end datetime data is in scope. Format: YYYY-MM-DD HH:MM:SS. Default: now.")

    metrics_subparsers = parser.add_subparsers(dest='metric_target')
 
    alert_parser = metrics_subparsers.add_parser("alerts", help="alert based metrics")
    build_metric_alert_parser(alert_parser)

    event_parser = metrics_subparsers.add_parser("events", help="event based metrics. With no arguments will return all events")
    build_metric_event_parser(event_parser)


def create_histogram_string(data: dict) -> str:
    """A convenience function that creates a graph in the form of a string.

    Args:
        data: A dictionary, where the values are integers representing a count of the keys.

    Returns:
        A graph in string form, pre-formatted for raw printing.
    """

    assert isinstance(data, dict)
    for key in data.keys():
        assert isinstance(data[key], int)

    total_results = sum([value for value in data.values()])
    txt = ""

    # order keys for printing in order (purly ascetics)
    ordered_keys = sorted(data, key=lambda k: data[k])
    results = []

    # longest_key used to calculate how many white spaces should be printed
    # to make the graph columns line up with each other
    longest_key = 0
    for key in ordered_keys:
        value = data[key]
        longest_key = len(key) if len(key) > longest_key else longest_key
        # IMPOSING LIMITATION: truncating keys to 95 chars, keeping longest key 5 chars longer
        longest_key = 100 if longest_key > 100 else longest_key
        percent = value / total_results * 100
        results.append((key[:95], value, percent, u"\u25A0"*(int(percent/2))))

    # two for loops are ugly, but allowed us to count the longest_key -
    # so we loop through again to print the text
    for r in results:
        txt += "%s%s: %5s - %5s%% %s\n" % (int(longest_key - len(r[0]))*' ', r[0] , r[1],
                                            str(r[2])[:4], u"\u25A0"*(int(r[2]/2)))
    return txt

def execute_metric_arguments(db: pymysql.connections.Connection, args):
    """Logic for executing metric CLI arguments.
    """

    from .alerts import ( get_alerts_between_dates,
                                 VALID_ALERT_STATS, 
                                 FRIENDLY_STAT_NAME_MAP,
                                 statistics_by_month_by_dispo,
                                 generate_hours_of_operation_summary_table,
                                 generate_overall_summary_table,
                                 define_business_time
                                )
    from .alerts.users import ( get_all_users,
                                generate_user_alert_stats,
                                alert_quantities_by_user_by_month )
    from .alerts.alert_types import ( unique_alert_types_between_dates,
                                             count_quantites_by_alert_type,
                                             get_alerts_between_dates_by_type,
                                             generate_alert_type_stats,
                                             all_alert_types
                                            )

    from .events import ( get_events_between_dates,
                                 get_incidents_from_events,
                                 add_email_alert_counts_per_event
                                )

    from .helpers import ( get_companies,
                                  dataframes_to_archive_bytes_of_json_files,
                                  dataframes_to_xlsx_bytes
                                )

    # store tables for printing or writing
    tables = []

    if args.companies:
        valid_companies = []
        valid_companies = list(get_companies(db).values())

        for company in args.companies:
            if company not in valid_companies:
                logging.warning(f"{company} is not a valid company: {valid_companies}")
                args.companies.remove(company)
        if not args.companies:
            sys.exit(0)

    if args.business_hours:
        bh_settings = args.business_hours.split(',')
        if not bh_settings:
            logging.error(f"invalid business hour format: {args.business_hours}")
            sys.exit(1)
        start_hour = int(bh_settings[0])
        end_hour = int(bh_settings[1])
        time_zone = bh_settings[2]
        # NOTE: holidays remain default
        args.business_hours = define_business_time(start_hour, end_hour, time_zone)

    if args.metric_target == 'events':
        start_date = datetime.datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
        end_date = datetime.datetime.strptime(args.end_datetime, '%Y-%m-%d %H:%M:%S')
        events = get_events_between_dates(start_date, end_date, db, selected_companies=args.companies)
        if args.count_emails:
            add_email_alert_counts_per_event(events, db)

        if args.incidents or args.incidents_only:
            incidents = get_incidents_from_events(events)
            tables.append(incidents)

        if not args.incidents_only:
            events.drop(columns=['id'], inplace=True)
            tables.append(events)

    if args.metric_target == 'alerts':
        # The intention is to only get data that's needed while
        # allowing the user to express the widest range of possible options.

        users = {}
        user_ids = []
        if args.alert_metric_target == 'users':
            users = get_all_users(db)

            if args.list_users:
                analysts = pd.DataFrame.from_dict(users, orient='index')
                analysts.name = "Users"
                tables.append(analysts)

            if args.users:
                # only use specified users
                for username in args.users:
                    user_ids.extend([user_id for user_id, user in users.items() if username == user['username']])
            else:
                user_ids = [user_id for user_id in users.keys()]

            if args.total_alert_count_breakdown:
                start_date = datetime.datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
                end_date = datetime.datetime.strptime(args.end_datetime, '%Y-%m-%d %H:%M:%S')
                user_dispositions_per_month = alert_quantities_by_user_by_month(start_date, end_date, db)
                if args.users:
                    tables.append(user_dispositions_per_month[args.users])
                else:
                    tables.append(user_dispositions_per_month)

        if args.alert_metric_target == 'types':
            if args.overall_count_breakdown:
                start_date = datetime.datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
                end_date = datetime.datetime.strptime(args.end_datetime, '%Y-%m-%d %H:%M:%S')
                at_counts = count_quantites_by_alert_type(start_date, end_date, db)
                tables.append(at_counts)

            # does the user want specific alert_type statistics?
            at_arg_stats = [sarg[len('alert_type_stat_'):] for sarg, value in vars(args).items() if sarg.startswith('alert_type_stat_') and value is True]

            if args.list_alert_types or args.all_at_stats or at_arg_stats:
                start_date = datetime.datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
                end_date = datetime.datetime.strptime(args.end_datetime, '%Y-%m-%d %H:%M:%S')
                alert_types = unique_alert_types_between_dates(start_date, end_date, db)

                if args.list_alert_types:
                    print(f"Alert Types between '{args.start_datetime}' and '{args.end_datetime}':")
                    [print(f"\t{at}") for at in alert_types]
                    print()
                    print("All Alert Types:")
                    [print(f"\t{at}") for at in all_alert_types(db)]

                if args.types:
                    # only use specified alert types
                    alert_types = [at for at in alert_types if at in args.types]

                if args.all_at_stats or at_arg_stats:
                    start_date = datetime.datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
                    end_date = datetime.datetime.strptime(args.end_datetime, '%Y-%m-%d %H:%M:%S')
                    alert_type_map = get_alerts_between_dates_by_type(start_date, end_date, db, selected_companies=args.companies)

                    alert_type_stat_map = generate_alert_type_stats(alert_type_map, business_hours=args.business_hours)

                    for alert_type in alert_types:
                        if args.all_at_stats:
                            for stat in VALID_ALERT_STATS:
                                tables.append(alert_type_stat_map[alert_type][stat])
                        else:
                            for stat in at_arg_stats:
                                tables.append(alert_type_stat_map[alert_type][stat])

        # does the user want specific alert statistics?
        alert_arg_stats = [sarg[len('alert_stat_'):] for sarg, value in vars(args).items() if sarg.startswith('alert_stat_') and value is True]

        # only get alert data if we really needs it
        if args.alert_metric_target == 'users' or alert_arg_stats \
          or args.all_alert_stats or args.hours_of_operation or args.average_alert_cycletime_summary:
            start_date = datetime.datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
            end_date = datetime.datetime.strptime(args.end_datetime, '%Y-%m-%d %H:%M:%S')
            alerts = get_alerts_between_dates(start_date, end_date, db, selected_companies=args.companies)

        if args.alert_metric_target == 'users':
            all_user_stat_map = generate_user_alert_stats(alerts, users, business_hours=args.business_hours)

            for user_id in user_ids:
                if args.all_user_stats:
                    for stat in VALID_ALERT_STATS:
                        tables.append(all_user_stat_map[user_id][stat])
                else:
                    user_arg_stats = [sarg[len('user_stat_'):] for sarg, value in vars(args).items() if sarg.startswith('user_stat_') and value is True]
                    for stat in user_arg_stats:
                        tables.append(all_user_stat_map[user_id][stat])

        if alert_arg_stats or args.all_alert_stats:
            alert_stat_map = statistics_by_month_by_dispo(alerts, business_hours=args.business_hours)

            if args.all_alert_stats:
                for stat in VALID_ALERT_STATS:
                    alert_stat_map[stat].name = FRIENDLY_STAT_NAME_MAP[stat]
                    tables.append(alert_stat_map[stat])
            else:
                for stat in alert_arg_stats:
                    alert_stat_map[stat].name = FRIENDLY_STAT_NAME_MAP[stat]
                    tables.append(alert_stat_map[stat])

        if args.hours_of_operation:
            if not args.business_hours:
                # business hours are required
                args.business_hours = define_business_time()
            hop_df = generate_hours_of_operation_summary_table(alerts.copy(), args.business_hours)
            if args.fileout_format:
                tables.append(hop_df)
            else:
                stdout_like(hop_df, format=args.stdout_format)

        if args.average_alert_cycletime_summary:
            if not args.business_hours:
                # business hours are required
                args.business_hours = define_business_time()
            sla_df = generate_overall_summary_table(alerts.copy(), args.business_hours)
            if args.fileout_format:
                tables.append(sla_df)
            else:
                stdout_like(sla_df, format=args.stdout_format)

    # output
    if args.fileout_format and tables:
        time_stamp = str(datetime.datetime.now().timestamp())
        time_stamp = time_stamp[:time_stamp.rfind('.')]
        filename = f"ACE_metrics_{time_stamp}"

        if args.fileout_format == 'xls':
            if args.filename:
                filename = args.filename
            else:
                filename += ".xlsx"
            with open(filename, 'wb') as fp:
                fp.write(dataframes_to_xlsx_bytes(tables))
            if os.path.exists(filename):
                print(f" + wrote {filename}")
        if args.fileout_format == 'json':
            if args.filename:
                filename = args.filename
            else:
                filename += ".tar.gz"
            with open(filename, 'wb') as fp:
                fp.write(dataframes_to_archive_bytes_of_json_files(tables))
            if os.path.exists(filename):
                print(f" + wrote {filename}")
    else:
        for table in tables:
            stdout_like(table, format=args.stdout_format)

def cli_metrics():
    """Main entry point for metrics on the CLI.
    """

    from .helpers import connect_to_database
    from .config import load_config, DEFAULT_CONFIG_PATHS

    parser = argparse.ArgumentParser(description="CLI Interface to ACE Metrics")
    parser.add_argument('-d', '--debug', action='store_true', help="Turn on debug logging.")
    parser.add_argument('-cp', '--config-path', action='store', help="Path to config defining ACE db connection.")

    build_metric_parser(parser)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    config_paths = DEFAULT_CONFIG_PATHS
    if args.config_path:
        if not os.path.exists(args.config_path):
            logging.error(f"{args.config_path} does not exist.")
            return False
        config_paths.append(args.config_path) 

    config = load_config(config_paths)
    if not config:
        logging.error("You must define and supply a configuration. See `ace-metrics -h | grep config`")
        return False

    database_config = config['database_default']

    db = connect_to_database(database_config)

    return execute_metric_arguments(db, args)
