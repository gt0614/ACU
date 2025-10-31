
# ALMA Oracle Export Integration

This project extracts student data from an Oracle database, generates XML files, archives them, and optionally delivers them to a network share. It supports multiple environments and is Docker-ready.

---

## ✅ Prerequisites

Install this before installing `cx_Oracle`:

- **Microsoft C++ Build Tools**
  - During installation, select:
    - **Desktop development with C++**
    - Include **MSVC v142 or later** and **Windows SDK**

Restart the terminal and retry:

```bash
pip install cx_Oracle==8.1.0
```

---

## 🛠️ Setup

Navigate to the `alma` directory and run:

```bash
python -m venv .venv
.\.venv\Scriptsctivate
pip install -r requirements.txt
```

---

## 📁 Project Structure

```
BANNER-INTEGRATIONS/
└── alma
    ├── app/
    │   ├── data/
    │   │   └── archive/
    │   └── log/
    ├── src/
    │   ├── alma_extract_main.py
    │   └── config.ini
    ├── tests/
    ├── requirements.txt
    ├── Dockerfile
    ├── README.md
    └── .gitignore
```

---

## ⚙️ Configuration

Edit `src/config.ini` to define database and delivery settings:

```ini
[DEV]
db_url = db.devxe.acu.edu.au
db_port = 1521
db_name = DEVXE
db_username = acu
db_password = *

[PREPROD]
db_url = db.preprodxe.acu.edu.au
db_port = 1521
db_name = PREPRDXE
db_username = acu
db_password = *

[PROD]
db_url = db.prodxe.acu.edu.au
db_port = 1521
db_name = PRODXE
db_username = acu
db_password = *

[delivery]
local_dir = app/data
log_dir = app/log
network_dir = /mnt/student/
filename_prefix = student
```

---

## 🧪 Running Locally

```bash
python src/alma_extract_main.py --environment PREPROD --network_dir /mnt/student
```

---

## 🐳 Docker Instructions

### Build Image
```bash
docker build -t alma-export:0.1 .
```

### Run Container
```bash
docker run -it --rm --name alma-export -w /var/tmp alma-export:0.1   python src/alma_extract_main.py --environment PREPROD --network_dir /mnt/student
```

---

## 📦 Oracle Instant Client Setup

The Dockerfile installs Oracle Instant Client 21.1 and configures:

```Dockerfile
ENV ORACLE_HOME=/opt/oracle/instantclient_21_1
ENV LD_LIBRARY_PATH=$ORACLE_HOME
```

---

## 📄 Requirements

```
cx-Oracle==8.1.0
configparser
lxml
```

---

## 📌 Notes

- XML files are archived to `app/data/archive`.
- Old files in `app/data` are cleaned up automatically (older than 7 days).
- Logging is written to `app/log/alma_oracle_export.log`.
- Network delivery is optional and controlled via `--network_dir`.

---

## 🛠️ Troubleshooting

### 1. ❗ Oracle Client Not Found
**Error:** `DPI-1047: Cannot locate a 64-bit Oracle Client library`

**Fix:**
- Ensure Oracle Instant Client is installed.
- Set environment variables correctly:
  ```bash
  set PATH=C:\oracle\instantclient_21_19;%PATH%
  ```

### 2. ❗ Permission Denied on Network Share
**Error:** `PermissionError: [Errno 13] Permission denied: '/mnt/student'`

**Fix:**
- Ensure the network share is mounted and accessible.
- Run the script with appropriate permissions.
- Verify the path exists and is writable.

### 3. ❗ XML Generation Errors
**Error:** `Oracle or XML error: ...`

**Fix:**
- Check database connectivity.
- Ensure required tables and data exist.
- Validate that all required fields are populated.

### 4. ❗ File Not Found or Invalid Path
**Error:** `FileNotFoundError` or `OSError`

**Fix:**
- Ensure all directories in `config.ini` exist or are created by the script.
- Avoid using quotes around paths in `config.ini`.

