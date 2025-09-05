from dotenv import load_dotenv
from os import getenv
from sys import exit
from importlib.util import find_spec
import pymysql.cursors
from subprocess import run
import logging
from urllib import request
import re

load_dotenv()

LOG_LEVEL = getenv("LOG_LEVEL", "ERROR").upper()

logger = logging.getLogger("x-ray")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.ERROR))
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s | %(levelname)s > %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False

dependencies = ["aiosmtpd", "pymysql", "dkim", "dns", "uuid_utils", "dotenv", "cryptography"]

def log(message, priority='info'):
  log_func = getattr(logger, priority.lower(), logger.info)
  log_func(message)
  #run(['postlog', '-p', priority, '-t', 'xray', message])

for i in dependencies:
  if find_spec(i) is None:
    log(f"Required dependency '{i}' is not installed.", "error")
    exit(1)

VERSION = "1.0.0"

PORT = int(getenv("PORT", 10031))
HOST = getenv("HOST", "127.0.0.1")

DB_HOST = getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(getenv("DB_PORT", 3306))
DB_DATABASE = getenv("DB_DATABASE")
DB_USERNAME = getenv("DB_USERNAME")
DB_PASSWORD = getenv("DB_PASSWORD")

ENCRYPTION = getenv("ENCRYPTION", "false").lower() in ("true", "1", "yes", "on")

SCORE_RSPAMD_SPAM = float(getenv("SCORE_RSPAMD_SPAM", 3))
SCORE_CLAMAV_VIRUS = float(getenv("SCORE_CLAMAV_VIRUS", 5))
SCORE_SPF_ERR = float(getenv("SCORE_SPF_ERR", 3))
SCORE_SPF_WARN = float(getenv("SCORE_SPF_WARN", 1.5))
SCORE_DMARC_ERR = float(getenv("SCORE_DMARC_ERR", 4))
SCORE_MX_WARN = float(getenv("SCORE_MX_WARN", 1))
SCORE_RDNS_WARN = float(getenv("SCORE_RDNS_WARN", 1))
SCORE_DKIM_NO = float(getenv("SCORE_DKIM_NO", 1))
SCORE_DKIM_ERR = float(getenv("SCORE_DKIM_ERR", 3))
SCORE_RBL_ERR = float(getenv("SCORE_RBL_ERR", 1.5))

def check_db():
  if not DB_USERNAME or not DB_PASSWORD:
    log("DB_USERNAME and DB_PASSWORD must be defined in environment.", "critical")
    exit(1)
  
  try:
    connection = pymysql.connect(host=DB_HOST,
                              port=DB_PORT,
                              user=DB_USERNAME,
                              password=DB_PASSWORD,
                              database=DB_DATABASE,
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)

    with connection.cursor() as cursor:
      sql_get = "SELECT @version;"
      cursor.execute(sql_get)
      result = cursor.fetchone()
  except Exception as e:
    log(f"Unable to connect to the database. Please check your credentials and database status.", "critical")
    log(e, "debug")
    exit(1)