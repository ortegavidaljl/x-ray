import pymysql.cursors
import uuid_utils as uuid
import json
from utils.config import log, DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE
# Connect to the database

async def save_report(sent_to, general_report, spamassassin_report, authentication_report, rbl_report):
   
  connection = pymysql.connect(host=DB_HOST,
                              user=DB_USERNAME,
                              password=DB_PASSWORD,
                              database=DB_DATABASE,
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)
  
  try:
    with connection.cursor() as cursor:
      sql = "INSERT INTO reports (id, account_id, general, spamassassin, authentication, rbl) VALUES (%s, (SELECT id FROM accounts WHERE name = %s), %s, %s, %s, %s);"
      cursor.execute(sql, (str(uuid.uuid7()), sent_to, json.dumps(general_report), json.dumps(spamassassin_report), json.dumps(authentication_report), json.dumps(rbl_report)))
      connection.commit()
  finally:
    connection.close()