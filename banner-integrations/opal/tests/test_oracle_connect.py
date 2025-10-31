import os
import configparser
import cx_Oracle
import argparse

# -------------------------------
# Resolve base directory of the project
# -------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# -------------------------------
# Initialize Oracle Client for Thick mode (only outside Docker)
# -------------------------------
if os.getenv("RUNNING_IN_DOCKER") != "true":
    instant_client_dir = r"C:\oracle\instantclient_21_19"
    cx_Oracle.init_oracle_client(lib_dir=instant_client_dir)

# -------------------------------
# Load configuration from config.ini
# -------------------------------
def get_config():
    config_path = os.path.join(BASE_DIR, "src", "config.ini")
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

# -------------------------------
# Test Oracle Connection
# -------------------------------
def test_oracle_connection(env):
    config = get_config()
    if env not in config:
        print(f"Environment '{env}' not found in config.ini")
        return

    env_conf = config[env]
    dsn = f"{env_conf['db_url']}:{env_conf['db_port']}/{env_conf['db_name']}"

    try:
        conn = cx_Oracle.connect(
            user=env_conf["db_username"],
            password=env_conf["db_password"],
            dsn=dsn
        )
        print(f"Connection successful to {env} ({dsn})")
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

# -------------------------------
# Parse command-line arguments
# -------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Oracle Connection")
    parser.add_argument("--environment", required=True, choices=["DEV", "PREPROD", "PROD"], help="Target environment")
    args = parser.parse_args()

    test_oracle_connection(args.environment)