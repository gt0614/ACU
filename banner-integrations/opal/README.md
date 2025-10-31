
# OPAL Oracle Export Integration

This project extracts student data from an Oracle database, generates a `.dat` flat file, archives it, and optionally delivers it to an SFTP site. It supports multiple environments and is Docker-ready.

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

Navigate to the `opal` directory and run:

```bash
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

---

## 📁 Project Structure

```
BANNER-INTEGRATIONS/
└── opal
    ├── app/
    │   ├── data/
    │   │   └── archive/
    │   └── log/
    ├── src/
    │   ├── config.ini
    │   └── opal_extract_main.py
    ├── tests/
    │   └── test_oracle_connect.py
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
local_dir = "app/data"
log_dir = "app/log"
filename_prefix = "out_put"
```

---

## 🧪 Running Locally

### ✅ Without SFTP Details
Generate and archive the file locally:

```bash
python src/opal_extract_main.py --environment DEV
```

---

### ✅ With SFTP Details
Generate, archive, and upload the file to an SFTP server:

```bash
python src/opal_extract_main.py   --environment DEV   --sftp_host sftp.example.com   --sftp_port 22   --sftp_username myuser   --sftp_private_key /path/to/key.ppk   --sftp_remote_dir incoming/
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
paramiko==3.4.0
```

---

## 📌 Notes
- `.dat` flat files are archived to `app/data/archive`.
- Old files in `app/data` are cleaned up automatically (older than 7 days).
- Logging is written to `app/log/opal_oracle_export.log`.
- SFTP delivery is optional and controlled via:
  `--sftp_host`, `--sftp_port`, `--sftp_username`, `--sftp_private_key`, `--sftp_remote_dir`.

---

## 🛠️ Troubleshooting

### 1. CryptographyDeprecationWarning
```
TripleDES has been moved to cryptography.hazmat.decrepit.ciphers.algorithms.TripleDES
```
**Cause:** Paramiko uses deprecated TripleDES cipher.  
**Fix:** Upgrade `paramiko` and `cryptography`:
```bash
pip install --upgrade paramiko cryptography
```
Or ignore warnings:
```python
import warnings
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
```

---

### 2. Virtual Environment Issues
```
Fatal error in launcher: Unable to create process using ...
```
**Cause:** Corrupted `.venv` or wrong path.  
**Fix:**
```bash
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scriptsctivate
pip install -r requirements.txt
```

---

### 3. SFTP Transfer Fails
```
SFTP transfer failed: [Errno 2] No such file or directory
```
**Cause:** Incorrect path to private key or remote directory.  
**Fix:**
- Ensure the private key path is correct and accessible.
- Ensure the remote directory exists and the user has write permissions.
- Use absolute paths for the private key.

```
SFTP transfer failed: Authentication failed.
```
**Cause:** Invalid username or private key.  
**Fix:**
- Verify the username and private key match the server configuration.
- Check if the key requires a passphrase.

