import os
import json
import logging

from configparser import ConfigParser

# for CLI use
HOME_PATH = os.path.dirname(os.path.abspath(__file__))
ETC_DIR = os.path.join(HOME_PATH, 'etc')

DEFAULT_CONFIG = os.path.join(HOME_PATH, ETC_DIR, 'config.ini')
GLOBAL_CONFIG_PATH = '/opt/ace/etc/ace_metrics.ini'
USER_CONFIG_PATH = os.path.join(os.path.expanduser("~"),'.config', 'ace', 'metrics.ini')
ENV_CONFIG_PATH = os.environ['ACE_METRICS_CONFIG_PATH'] if 'ACE_METRICS_CONFIG_PATH' in os.environ else None

# Later configs override earlier configs
DEFAULT_CONFIG_PATHS = [DEFAULT_CONFIG, GLOBAL_CONFIG_PATH, USER_CONFIG_PATH]
if ENV_CONFIG_PATH is not None:
    DEFAULT_CONFIG_PATHS.append(ENV_CONFIG_PATH)

def load_config(config_paths: list = DEFAULT_CONFIG_PATHS) -> ConfigParser:
    """Load ACE Metric configuration.

    Args:
      config_paths: List of configuration paths.

    Returns:
      A ConfigParser  
    """

    config = ConfigParser()
    finds = []
    for cp in config_paths:
        if cp and os.path.exists(cp):
            logging.debug("Found config file at {}.".format(cp))
            finds.append(cp)
    if not finds:
        logging.error("Didn't find any config files defined at these paths: {}".format(config_paths))
        return False

    config.read(finds)

    return config
