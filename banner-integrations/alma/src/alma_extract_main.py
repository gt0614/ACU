import os
import zipfile
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import configparser
import cx_Oracle
from lxml import etree
import shutil
import time
import argparse

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
    parser = argparse.ArgumentParser(description="ALMA Extract Script")
    parser.add_argument("--environment", required=True, choices=["DEV", "PREPROD", "PROD"], help="Target environment")
    parser.add_argument("--network_dir", required=False, help="Optional network directory for ZIP delivery")
    return parser.parse_args()

# -------------------------------
# Fetch source data
# -------------------------------

def fetch_students(conn):
    cursor = conn.cursor()
    pidms = ['372080', '375036', '376796', '379722', '383079',
         '386411', '386566', '388566', '388941', '389411']

    query = f"""
    SELECT SPRIDEN_PIDM, SPRIDEN_ID, SPRIDEN_FIRST_NAME, SPRIDEN_MI, SPRIDEN_LAST_NAME,
           USER_NAME, USER_TITLE, GENDER, USER_GROUP, CAMPUS_CODE, PREFERRED_LANGUAGE,
           USER_BIRTH_DATE, EXPIRY_DATE, PURGE_DATE, BARCODE, STATUS
    FROM ALMA_STUDENT_CHANGED
    WHERE SPRIDEN_PIDM IN ({','.join([':{}'.format(i+1) for i in range(len(pidms))])})
    """

    cursor.execute(query, pidms)
    # cursor.execute("SELECT SPRIDEN_PIDM, SPRIDEN_ID, SPRIDEN_FIRST_NAME, SPRIDEN_MI, SPRIDEN_LAST_NAME, USER_NAME, USER_TITLE, GENDER, USER_GROUP, CAMPUS_CODE, PREFERRED_LANGUAGE, USER_BIRTH_DATE, EXPIRY_DATE, PURGE_DATE, BARCODE, STATUS FROM ALMA_STUDENT_CHANGED WHERE SPRIDEN_PIDM IN (
    # '372080'
    # ,'375036'
    # ,'376796'
    # ,'379722'
    # ,'383079'
    # ,'386411'
    # ,'386566'
    # ,'388566'
    # ,'388941'
    # ,'389411'
    # )")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def preload_addresses(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SPRADDR_PIDM, PREFERRED, SPRADDR_STREET_LINE1, SPRADDR_STREET_LINE2, SPRADDR_STREET_LINE3, SPRADDR_CITY, SPRADDR_STAT_CODE, SPRADDR_ZIP, ADDRESS_TYPE, START_DATE, END_DATE
        FROM ALMA_ADDRESS_MA
    """)
    columns = [col[0] for col in cursor.description]
    address_dict = {}
    for row in cursor.fetchall():
        pidm = row[0]
        address_dict.setdefault(pidm, []).append(dict(zip(columns[1:], row[1:])))
    return address_dict

def preload_emails(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT EMAIL_PIDM, PREFERRED, EMAIL_ADDRESS, EMAIL_TYPE
        FROM ALMA_EMAIL
    """)
    columns = [col[0] for col in cursor.description]
    email_dict = {}
    for row in cursor.fetchall():
        pidm = row[0]
        email_dict.setdefault(pidm, []).append(dict(zip(columns[1:], row[1:])))
    return email_dict

def preload_phones(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT PHONE_PIDM, PREFERRED, PHONE_NUMBER, PHONE_TYPE
        FROM ALMA_PHONE_HOME
    """)
    columns = [col[0] for col in cursor.description]
    phone_dict = {}
    for row in cursor.fetchall():
        pidm = row[0]
        phone_dict.setdefault(pidm, []).append(dict(zip(columns[1:], row[1:])))
    return phone_dict

# -------------------------------
# Build XML structure from student data
# -------------------------------

def add_element_if_value(parent, tag, value):
    if value and str(value).strip():
        etree.SubElement(parent, tag).text = str(value)

def build_xml(students, address_dict, email_dict, phone_dict):
    root = etree.Element("users")
    for student in students:
        user = etree.SubElement(root, "user")

        # Mandatory and basic fields
        etree.SubElement(user, "record_type").text = "PUBLIC"
        add_element_if_value(user, "primary_id", student.get("SPRIDEN_ID"))
        add_element_if_value(user, "first_name", student.get("SPRIDEN_FIRST_NAME"))
        add_element_if_value(user, "middle_name", student.get("SPRIDEN_MI"))
        add_element_if_value(user, "last_name", student.get("SPRIDEN_LAST_NAME"))
        add_element_if_value(user, "full_name", student.get("USER_NAME"))
        add_element_if_value(user, "user_title", student.get("USER_TITLE"))
        add_element_if_value(user, "gender", student.get("GENDER"))
        add_element_if_value(user, "user_group", student.get("USER_GROUP"))
        add_element_if_value(user, "campus_code", student.get("CAMPUS_CODE"))
        add_element_if_value(user, "preferred_language", student.get("PREFERRED_LANGUAGE"))
        add_element_if_value(user, "birth_date", student.get("USER_BIRTH_DATE"))
        add_element_if_value(user, "expiry_date", student.get("EXPIRY_DATE"))
        add_element_if_value(user, "purge_date", student.get("PURGE_DATE"))
        etree.SubElement(user, "account_type").text = "EXTERNAL"
        add_element_if_value(user, "external_id", student.get("SPRIDEN_ID"))
        add_element_if_value(user, "status", student.get("STATUS"))

        # Contact Info
        contact_info = etree.SubElement(user, "contact_info")

        # Addresses
        addresses_elem = etree.SubElement(contact_info, "addresses")
        pidm = int(student["SPRIDEN_PIDM"])  # Ensure it's an integer
        for addr in address_dict.get(pidm, []):
        #for addr in address_dict.get(student["SPRIDEN_PIDM"], []):
            address_elem = etree.SubElement(addresses_elem, "address")
            if addr.get("PREFERRED"):
                address_elem.set("preferred", str(addr.get("PREFERRED")).lower())
            add_element_if_value(address_elem, "line1", addr.get("SPRADDR_STREET_LINE1"))
            add_element_if_value(address_elem, "line2", addr.get("SPRADDR_STREET_LINE2"))
            add_element_if_value(address_elem, "line3", addr.get("SPRADDR_STREET_LINE3"))
            add_element_if_value(address_elem, "city", addr.get("SPRADDR_CITY"))
            add_element_if_value(address_elem, "state_province", addr.get("SPRADDR_STAT_CODE"))
            add_element_if_value(address_elem, "postal_code", addr.get("SPRADDR_ZIP"))
            if addr.get("ADDRESS_TYPE"):
                address_types_elem = etree.SubElement(address_elem, "address_types")
                add_element_if_value(address_types_elem, "address_type", addr.get("ADDRESS_TYPE"))
            add_element_if_value(address_elem, "start_date", addr.get("START_DATE"))
            add_element_if_value(address_elem, "end_date", addr.get("END_DATE"))

        # Emails
        emails_elem = etree.SubElement(contact_info, "emails")
        pidm = int(student["SPRIDEN_PIDM"])  # Ensure it's an integer
        for email in email_dict.get(pidm, []):
        #for email in email_dict.get(student["SPRIDEN_PIDM"], []):
            email_elem = etree.SubElement(emails_elem, "email")
            if email.get("PREFERRED"):
                email_elem.set("preferred", str(email.get("PREFERRED")).lower())
            add_element_if_value(email_elem, "email_address", email.get("EMAIL_ADDRESS"))
            if email.get("EMAIL_TYPE"):
                email_types_elem = etree.SubElement(email_elem, "email_types")
                add_element_if_value(email_types_elem, "email_type", email.get("EMAIL_TYPE"))

        # Phones
        phones_elem = etree.SubElement(contact_info, "phones")
        pidm = int(student["SPRIDEN_PIDM"])  # Ensure it's an integer
        for phone in phone_dict.get(pidm, []):
        #for phone in phone_dict.get(student["SPRIDEN_PIDM"], []):
            phone_elem = etree.SubElement(phones_elem, "phone")
            if phone.get("PREFERRED"):
                phone_elem.set("preferred", str(phone.get("PREFERRED")).lower())
            add_element_if_value(phone_elem, "phone_number", phone.get("PHONE_NUMBER"))
            if phone.get("PHONE_TYPE"):
                phone_types_elem = etree.SubElement(phone_elem, "phone_types")
                add_element_if_value(phone_types_elem, "phone_type", phone.get("PHONE_TYPE"))

        # User Identifiers
        user_identifiers_elem = etree.SubElement(user, "user_identifiers")
        if student.get("BARCODE"):
            barcode_elem = etree.SubElement(user_identifiers_elem, "user_identifier")
            etree.SubElement(barcode_elem, "id_type").text = "01"
            add_element_if_value(barcode_elem, "value", student.get("BARCODE"))
        if student.get("SPRIDEN_ID"):
            spriden_elem = etree.SubElement(user_identifiers_elem, "user_identifier")
            etree.SubElement(spriden_elem, "id_type").text = "02"
            add_element_if_value(spriden_elem, "value", student.get("SPRIDEN_ID"))

        # User Roles
        user_roles_elem = etree.SubElement(user, "user_roles")
        user_role_elem = etree.SubElement(user_roles_elem, "user_role")
        etree.SubElement(user_role_elem, "status").text = "ACTIVE"
        etree.SubElement(user_role_elem, "scope").text = "61UNI_ACU"
        etree.SubElement(user_role_elem, "role_type").text = "200"

        # Parameters block (always present)
        parameters_elem = etree.SubElement(user_role_elem, "parameters")
        parameter_elem = etree.SubElement(parameters_elem, "parameter")
        etree.SubElement(parameter_elem, "type")
        etree.SubElement(parameter_elem, "value")

        # logging.info(f"Student PIDM: {student['SPRIDEN_PIDM']}")
        # logging.info(f"Addresses found: {len(address_dict.get(int(student['SPRIDEN_PIDM']), []))}")
        # logging.info(f"Emails found: {len(email_dict.get(int(student['SPRIDEN_PIDM']), []))}")
        # logging.info(f"Phones found: {len(phone_dict.get(int(student['SPRIDEN_PIDM']), []))}")

    return root

# -------------------------------
# Clean up XML content by removing unwanted declarations
# -------------------------------
def xml_cleanup(xml_path):
    with open(xml_path, "r", encoding="utf-8") as f:
        xml_content = f.read()
    xml_content = xml_content.replace("<?xml version='1.0' encoding='UTF-8'?>", "")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

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
# Main execution function
# -------------------------------
def main():
    # Parse arguments and load config
    args = parse_args()
    config = get_config()
    env_conf = config[args.environment]
    delivery_conf = config["delivery"]

    # Build Oracle DSN from config
    dsn = f"{env_conf['db_url']}:{env_conf['db_port']}/{env_conf['db_name']}"

    # Resolve local and log directories
    local_dir = os.path.normpath(os.path.join(BASE_DIR, delivery_conf["local_dir"].strip('"')))
    log_dir = os.path.normpath(os.path.join(BASE_DIR, delivery_conf["log_dir"].strip('"')))
    os.makedirs(local_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # Setup logging with rotation
    log_file_path = os.path.join(log_dir, "alma_oracle_export.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        ]
    )

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%d-%m-%Y-%H%M%S")
    filename_prefix = delivery_conf['filename_prefix'].strip('"')
    filename = f"{filename_prefix}-{timestamp}"
    xml_path = os.path.join(local_dir, f"{filename}.xml")
    zip_path = os.path.join(local_dir, f"{filename}.zip")

    # Setup archive directory
    archive_dir = os.path.join(local_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    archive_zip_path = os.path.join(archive_dir, os.path.basename(zip_path))

    # Connect to Oracle and generate XML
    try:
        logging.info(f"Connecting to Oracle DB: {env_conf['db_name']}")
        conn = cx_Oracle.connect(
            user=env_conf["db_username"],
            password=env_conf["db_password"],
            dsn=dsn
        )
        students = fetch_students(conn)
        logging.info(f"Fetched {len(students)} students")
        address_dict = preload_addresses(conn)
        email_dict = preload_emails(conn)
        phone_dict = preload_phones(conn)
        logging.info(f"Preloaded {sum(len(v) for v in address_dict.values())} addresses, {sum(len(v) for v in email_dict.values())} emails, {sum(len(v) for v in phone_dict.values())} phones")
        xml_root = build_xml(students, address_dict, email_dict, phone_dict)
        tree = etree.ElementTree(xml_root)
        tree.write(xml_path, encoding="utf-8", xml_declaration=False, pretty_print=True)
        conn.close()
        logging.info(f"XML written to {xml_path}")
    except Exception as e:
        logging.error(f"Oracle or XML error: {e}")
        return

    # Clean up XML formatting
    try:
        xml_cleanup(xml_path)
        logging.info("XML cleanup done")
    except Exception as e:
        logging.error(f"XML cleanup error: {e}")
        return

    # Zip the XML file
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(xml_path, arcname=os.path.basename(xml_path))
        logging.info(f"Zipped to {zip_path}")
    except Exception as e:
        logging.error(f"Zipping error: {e}")
        return

    # Archive the ZIP file
    try:
        shutil.copy2(zip_path, archive_zip_path)
        logging.info(f"Archived to {archive_zip_path}")
    except Exception as e:
        logging.error(f"Archiving error: {e}")

    # Optionally copy ZIP to network directory
    if args.network_dir:
        try:
            network_zip_path = os.path.join(args.network_dir, os.path.basename(zip_path))
            shutil.copy2(zip_path, network_zip_path)
            logging.info(f"Delivered to {network_zip_path}")
        except Exception as e:
            logging.error(f"Network delivery error: {e}")
    else:
        logging.info("No network_dir provided. Skipping delivery.")

    # Clean up old files from local directory
    cleanup_old_files(local_dir, days=7)

# -------------------------------
# Entry point
# -------------------------------
if __name__ == "__main__":
    main()

