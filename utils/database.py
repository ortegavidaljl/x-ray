import pymysql.cursors
import uuid_utils as uuid
import json
from utils.config import log, DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE, ENCRYPTION
import utils.encryption as encryption
# Connect to the database

async def save_report(report):

  sent_to = report['general']['sent_to']
  encryption_data = None
  encrypted_report = None
  report = json.dumps(report).encode('utf-8')

  connection = pymysql.connect(host=DB_HOST,
                              port=DB_PORT,
                              user=DB_USERNAME,
                              password=DB_PASSWORD,
                              database=DB_DATABASE,
                              charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)

  try:
    with connection.cursor() as cursor:

      if ENCRYPTION:
        # Obtain public key from the database
        sql_get = "SELECT public_key FROM accounts WHERE name = %s"
        cursor.execute(sql_get, (sent_to,))
        result = cursor.fetchone()
        public_key = result['public_key'] if result else None

        if public_key is None:
          log(f"No public key found for {sent_to}; Report won't be saved.", "error")
          return

        # Encrypt the report
        encrypted_report, nonce, key = encryption.encrypt_symmetric(report)
        report = None

        # Encrypt the symmetric decryption data with the public key
        encryption_data = encryption.encrypt_asymmetric(
          public_key,
          "der",
          nonce + key
        )

        encrypted_report = encrypted_report + encryption_data

      # Insertar el reporte
      sql_insert = "INSERT INTO reports (id, account_id, report, encrypted_report) VALUES (%s, (SELECT id FROM accounts WHERE name = %s), %s, %s);"
      cursor.execute(sql_insert, (str(uuid.uuid7()), sent_to, report, encrypted_report))
      connection.commit()
  finally:
    connection.close()