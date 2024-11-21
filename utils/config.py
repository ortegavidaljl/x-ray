from dotenv import dotenv_values
import sys
import importlib.util
import subprocess

dependencies = ["aiosmtpd", "pymysql", "asyncio", "dkim", "dns", "uuid_utils", "dotenv"]

for i in dependencies:
  if importlib.util.find_spec(i) is None:
    message=f"ERROR: Required dependency '{i}' is not installed."
    print(message)
    sys.exit(1)

config = dotenv_values(".env")

VERSION=0.8
PORT = int(config.get("PORT", 10031))
HOSTNAME = config.get("HOSTNAME", "127.0.0.1")

DB_HOST = config.get("DB_HOST", "127.0.0.1")
DB_PORT = int(config.get("DB_PORT", 3306))
DB_DATABASE = config.get("DB_DATABASE")
DB_USERNAME = config.get("DB_USERNAME")
DB_PASSWORD = config.get("DB_PASSWORD")

SCORE_SPAMASSASSIN_SPAM = float(config.get("SCORE_SPAMASSASSIN_SPAM", 3))
SCORE_SPF_ERR = float(config.get("SCORE_SPF_ERR", 3))
SCORE_SPF_WARN = float(config.get("SCORE_SPF_WARN", 1.5))
SCORE_MX_WARN = float(config.get("SCORE_MX_WARN", 1))
SCORE_RDNS_WARN = float(config.get("SCORE_RDNS_WARN", 1))
SCORE_DKIM_NO = float(config.get("SCORE_DKIM_NO", 1))
SCORE_DKIM_ERR = float(config.get("SCORE_DKIM_ERR", 3))
SCORE_RBL_ERR = float(config.get("SCORE_RBL_ERR", 1.5))

def check_db():
  if not DB_USERNAME or not DB_PASSWORD:
    message="ERROR: DB_USERNAME and DB_PASSWORD must be defined in '.env' file."
    print(message)
    sys.exit(1)

# This function lets us output data into the postfix log file.
def log(message, priority='info'):
  subprocess.run(['postlog', '-p', priority, '-t', 'xray', message])