import os
import argparse
import configparser
import cx_Oracle
import paramiko
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import shutil
import time

# -------------------------------
# Resolve base directory of the project
# -------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# -------------------------------
# Initialize Oracle Client for Thick mode (only outside Docker)
# -------------------------------
running_in_docker = os.getenv("RUNNING_IN_DOCKER", "true").lower()
 
if running_in_docker != "true":

# if os.getenv("RUNNING_IN_DOCKER") != "true":
    instant_client_dir = r"C:\\oracle\\instantclient_21_19"
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
# Parse command-line arguments
# -------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="OPAL Extract Script")
    parser.add_argument("--environment", required=True, choices=["DEV", "PREPROD", "PROD"], help="Target environment")
    parser.add_argument("--sftp_host")
    parser.add_argument("--sftp_port", type=int)
    parser.add_argument("--sftp_username")
    parser.add_argument("--sftp_private_key")
    parser.add_argument("--sftp_remote_dir")
    return parser.parse_args()

# -------------------------------
# Remove files older than a specified number of days
# -------------------------------
def cleanup_old_files(folder_path, days=7):
    cutoff_time = time.time() - (days * 86400)
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
            os.remove(file_path)

# -------------------------------
# Set up logging: console + rotating file handler
# -------------------------------
def setup_logging(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "opal_oracle_export.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        ]
    )

# -------------------------------
# Establish Oracle database connection using provided configuration
# -------------------------------
def get_oracle_connection(db_conf):
    try:
        dsn = cx_Oracle.makedsn(db_conf["db_url"], db_conf["db_port"], service_name=db_conf["db_name"])
        conn = cx_Oracle.connect(
            user=db_conf["db_username"],
            password=db_conf["db_password"],
            dsn=dsn
        )
        return conn
    except Exception as e:
        logging.error(f"Oracle connection failed: {e}")
        raise

# -------------------------------
# Fetch source data
# -------------------------------
def fetch_sftp_lines(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SFTP_LINE FROM ACU.SZBSFTP3 WHERE LINE_NO = 0")
        header_lines = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT SFTP_LINE FROM ACU.SZBSFTP3 WHERE LINE_NO = 1")
        body_lines = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return header_lines + body_lines
    except Exception as e:
        logging.error(f"Oracle fetch failed: {e}")
        raise

def fetch_file_name(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT FILE_NAME FROM ACU.SZBSFTP0 WHERE FILE_TYPE = 'put'")
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Oracle file name fetch failed: {e}")
        raise

# -------------------------------
# Write extracted lines to a flat file
# -------------------------------
def write_flat_file(lines, file_path):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(f"{line}\n")
        logging.info(f"Wrote flat file: {file_path}")
    except Exception as e:
        logging.error(f"File write failed: {e}")
        raise

# -------------------------------
# Archive a file by copying it to the specified directory
# -------------------------------
def archive_file(file_path, archive_dir):
    try:
        os.makedirs(archive_dir, exist_ok=True)
        archive_path = os.path.join(archive_dir, os.path.basename(file_path))
        shutil.copy2(file_path, archive_path)
        logging.info(f"Archived {file_path} to {archive_path}")
    except Exception as e:
        logging.error(f"Archiving failed: {e}")

# -------------------------------
# Upload a local file to a remote SFTP server 
# -------------------------------
def sftp_transfer(sftp_args, local_file, remote_file):
    try:
        key = paramiko.RSAKey.from_private_key_file(sftp_args["private_key"])
        transport = paramiko.Transport((sftp_args["host"], int(sftp_args["port"])))
        transport.connect(username=sftp_args["username"], pkey=key)
        sftp = paramiko.SFTPClient.from_transport(transport)
        remote_path = os.path.join(sftp_args["remote_dir"], remote_file)
        sftp.put(local_file, remote_path)
        sftp.close()
        transport.close()
        logging.info(f"Transferred {local_file} to SFTP {remote_path}")
    except Exception as e:
        logging.error(f"SFTP transfer failed: {e}")

# -------------------------------
# Main execution function
# -------------------------------
def main():
    # Parse arguments and load config
    args = parse_args()
    config = get_config()
    db_conf = config[args.environment]
    delivery_conf = config["delivery"]

    # Resolve local and log directories
    local_dir = delivery_conf.get("local_dir", "app/data").replace('"', '')
    log_dir = delivery_conf.get("log_dir", "app/log").replace('"', '')
    archive_dir = os.path.join(local_dir, "archive")
    setup_logging(log_dir)
    os.makedirs(local_dir, exist_ok=True)

    try:
        conn = get_oracle_connection(db_conf)
        file_ext = delivery_conf['file_ext'].strip('"').strip()
        file_name = fetch_file_name(conn)

        if not file_name:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            file_name = f"{delivery_conf['filename_prefix']}_{timestamp}{file_ext}"
        elif not file_name.endswith(file_ext):
            file_name = f"{file_name}{file_ext}"

        flat_file_path = os.path.join(local_dir, file_name)
        lines = fetch_sftp_lines(conn)
        conn.close()

        # Write the local flat file
        write_flat_file(lines, flat_file_path)

        # Archive the local flat file
        archive_file(flat_file_path, archive_dir)

        # Only upload to SFTP if all SFTP parameters are provided
        sftp_params = {
            "host": args.sftp_host,
            "port": args.sftp_port,
            "username": args.sftp_username,
            "private_key": args.sftp_private_key,
            "remote_dir": args.sftp_remote_dir
        }
        if all(sftp_params.values()):
            sftp_transfer(sftp_params, flat_file_path, file_name)
        else:
            logging.info("SFTP parameters not supplied, skipping upload.")

        logging.info("Process complete.")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)

    # Clean up old files from local directory
    cleanup_old_files(local_dir, days=7)

if __name__ == "__main__":
    main()