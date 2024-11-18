import mysql.connector
import uuid_utils as uuid
import json
from utils.config import log, DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE

async def save_report(sent_to, general_report, spamassassin_report, authentication_report, rbl_report):

  try:
    mydb = mysql.connector.connect(
      host=DB_HOST,
      port=DB_PORT,
      user=DB_USERNAME,
      password=DB_PASSWORD,
      database=DB_DATABASE
    )
  except mysql.connector.Error as err:
    log(f"Database connection error: {err}")
    return '451 Temporary server error'

  try:
    mycursor1 = mydb.cursor(prepared=True)
    sql = "INSERT INTO reports (id, account_id, general, spamassassin, authentication, rbl) VALUES (%s, (SELECT id FROM accounts WHERE name = %s), %s, %s, %s, %s);"
    mycursor1.execute(sql, (str(uuid.uuid7()), sent_to, json.dumps(general_report), json.dumps(spamassassin_report), json.dumps(authentication_report), json.dumps(rbl_report)))
    mydb.commit()
  except mysql.connector.Error as err:
    log(f"SQL execution error: {err}")
  finally:
    mycursor1.close()
    mydb.close()