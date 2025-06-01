#!/bin/python3.11

import os
import sys
import argparse
from utils.config import DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE, ENCRYPTION
import pymysql.cursors
from pymysql.err import IntegrityError
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import json

def generate_crypto_keys():
  private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
  )

  public_key = private_key.public_key()

  private_der = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
  )

  with open('xray_private.key', 'wb') as f:
    f.write(private_der)

  public_der = public_key.public_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
  )

  with open('xray_public.key', 'wb') as f:
    f.write(public_der)

def create_connection():
  return pymysql.connect(host=DB_HOST,
                        port=DB_PORT,
                        user=DB_USERNAME,
                        password=DB_PASSWORD,
                        database=DB_DATABASE,
                        charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor)

def generate_random_email(domain):
  random_bytes = os.urandom(16)  # 16 bytes aleatorios
  hex_str = random_bytes.hex()   # a hexadecimal
  parts = [hex_str[i:i+4] for i in range(0, len(hex_str), 4)]  # bloques de 4
  random_username = f"{parts[0]}-{parts[1]}"
  new_account = f"{random_username}@{domain}"
  return new_account

def create_domain():
  connection = create_connection()
  
  try:
    with connection.cursor() as cursor:
      is_domain_active = 0
      sql_get = "SELECT COUNT(*) as 'total_domains' FROM domains;"
      cursor.execute(sql_get)
      result = cursor.fetchone()

      if result['total_domains'] == 0:
        is_domain_active = 1

      sql_insert = "INSERT INTO domains (name, active) VALUES (%s, %s);"
      cursor.execute(sql_insert, (args.name, is_domain_active))
      connection.commit()
  except IntegrityError as e:
    print(f"Domain {args.name} already exists.")
    connection.rollback()
  finally:
    connection.close()

def create_account():
  connection = create_connection()
  public_key = None

  if ENCRYPTION:
    if not os.path.exists("./xray_public.key") or not os.path.exists("./xray_private.key"):
      generate_crypto_keys()

    with open("./xray_public.key", "rb") as f:
      public_key = f.read()
  
  try:
    with connection.cursor() as cursor:
      sql_get = "SELECT id, name FROM domains WHERE active = 1;"
      cursor.execute(sql_get)
      result = cursor.fetchone()

      account_name = generate_random_email(result['name'])

      sql_insert = "INSERT INTO accounts (domain_id, name, public_key) VALUES (%s, %s, %s);"
      cursor.execute(sql_insert, (result['id'], account_name, public_key))
      connection.commit()
      print(f"Account created: {account_name}")
  finally:
    connection.close()
    
def delete_domain():
  connection = create_connection()
  
  try:
    with connection.cursor() as cursor:
      sql_delete = "DELETE FROM domains WHERE name = %s;"
      cursor.execute(sql_delete, (args.name,))
      connection.commit()
  finally:
    connection.close()

def delete_account():
  connection = create_connection()
  
  try:
    with connection.cursor() as cursor:
      sql_delete = "DELETE FROM accounts WHERE name = %s;"
      cursor.execute(sql_delete, (args.name,))
      connection.commit()
  finally:
    connection.close()

def check_account():
  connection = create_connection()

  try:
    with connection.cursor() as cursor:
      sql_get = "SELECT count(id) as count FROM accounts WHERE name = %s;"
      cursor.execute(sql_get, (args.name,))
      result = cursor.fetchone()

      if result['count'] == 0:
        print(f"Account {args.name} does not exist.")
  finally:
    connection.close()

def check_domain():
  connection = create_connection()

  try:
    with connection.cursor() as cursor:
      sql_get = "SELECT count(id) as count FROM domains WHERE name = %s;"
      cursor.execute(sql_get, (args.name,))
      result = cursor.fetchone()

      if result['count'] == 0:
        print(f"Domain {args.name} does not exist.")
  finally:
    connection.close()

def process_authentication(nombre, datos):
  mensaje = datos.get("message", "").lower()
  if "ok" in mensaje:
      status_icon = "\033[92m[✓]\033[0m All good — tests passed like a charm."
  elif "warn" in mensaje:
      status_icon = "\033[93m[!]\033[0m Heads up — something might need your attention."
  elif "err" in mensaje or "fail" in mensaje:
      status_icon = "\033[91m[✗]\033[0m Uh-oh — test failed or error found."
  else:
      status_icon = "\033[94m[?]\033[0m Not sure what happened — unknown status."

  print(f"\n\033[1;34m >    {nombre.upper()} \033[0m")
  print("‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
  print(f"{status_icon} \n")

  for test in datos.get("tests", []):
    test_name = test["name"]
    result = test["result"]

    print(f"• {test_name.capitalize()} test:")

    if isinstance(result, list):
      for item in result:
        if isinstance(item, list):  # para pares tipo [clave, valor]
          print(f"   - {item[0]} {item[1]}")
        else:
          print(f"   {item}")
    elif isinstance(result, str):
      for linea in result.strip().splitlines():
        print(f"   {linea}")
    else:
      if test_name == "header":
        for clave, valor in test['result'].items():
          print(f"   - {clave.replace('_', ' ').capitalize()}: {valor}")
      else:
        print(f"   {result}")


def get_report():
  if ENCRYPTION:
    if not os.path.exists("./xray_public.key") and not os.path.exists("./xray_private.key"):
      print(f"Asymmetric keys not found; Can't get nor decipher reports. Create an account first and send it a report.")
      exit(1)

  connection = create_connection()

  try:
    with connection.cursor() as cursor:
      if args.name:
        if ENCRYPTION:
          with open("./xray_public.key", "rb") as f:
            public_key = f.read()
            sql_get = "SELECT id FROM accounts WHERE name = %s AND public_key = %s;"
            cursor.execute(sql_get, (args.name, public_key))
        else:
          sql_get = "SELECT id FROM accounts WHERE name = %s;"
          cursor.execute(sql_get, (args.name,))
      
        result = cursor.fetchone()

        if result['id'] == None:
          print(f"Account {args.name} does not exist or the associated cryptographic key does not match.")
          exit(1)

        sql_get = "SELECT id, created_at FROM reports WHERE account_id = %s ORDER BY created_at DESC;"
        cursor.execute(sql_get, (result['id'],))

        result_history = cursor.fetchall()

        if ENCRYPTION:
          sql_get = "SELECT id, encrypted_report as report FROM reports WHERE account_id = %s ORDER BY created_at DESC LIMIT 1;"
        else:
          sql_get = "SELECT id, report FROM reports WHERE account_id = %s ORDER BY created_at DESC LIMIT 1;"
        cursor.execute(sql_get, (result['id'],))

        result = cursor.fetchone()

        if not result:
          print(f"Report not found.")
          exit(1)
        
      else:
        if ENCRYPTION:
          sql_get = "SELECT id, account_id, encrypted_report as report FROM reports WHERE id = %s ORDER BY created_at DESC LIMIT 1;"
        else:
          sql_get = "SELECT id, account_id, report FROM reports WHERE id = %s ORDER BY created_at DESC LIMIT 1;"
        cursor.execute(sql_get, (args.id,))

        result = cursor.fetchone()

        if not result:
          print(f"Report not found.")
          exit(1)

        sql_get = "SELECT id, created_at FROM reports WHERE account_id = %s ORDER BY created_at DESC;"
        cursor.execute(sql_get, (result['account_id'],))

        result_history = cursor.fetchall()
      
      report_data = json.loads(result['report'])

      print("\n\033[1;34m  🗂️   >   ALL REPORTS \033[0m")
      print("‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
      for report_history_entry in result_history:
        line = f"{report_history_entry['id']} @ {report_history_entry['created_at']}"
        if report_history_entry['id'] == result['id']:
          print(f"\033[4;33m📂 {line}\033[0m")
        else:
          print(f"📁 {line}")

      print("\n\033[1;34m  🧪   >   RESULTS \033[0m")
      print("‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
      general = report_data["general"]
      print(f"{general['header']}")
      print(f"Score: {general['score']} / {general['max_score']}")

      print("\n\033[1;34m  ✉️   >   YOUR MESSAGE \033[0m")
      print("‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
      print(f"Received on: {general['message_date']}")
      print(f"Sender: {general['sent_from']}")
      print(f"Recipient: {general['sent_to']}")
      print(f"Processed in: {general['processed_in']} seconds")

      print("\n\033[1;34m  🧭   >   MAIL TRACE \033[0m")
      print("‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
      trace = list(reversed(general.get("trace", [])))
      for i, hop in enumerate(trace):
          at = hop.get("at", "Unknown time")
          _from = hop.get("from", None)
          to = hop.get("to", "Unknown recipient")

          # Determinar color según posición
          if i == 0:
              color = "(START) \033[93m"  # Amarillo para el origen
          elif i == len(trace) - 1:
              color = "(END) \033[92m"  # Verde para el destino final
          else:
              color = "\033[94m"  # Azul para intermedios

          if _from:
              from_str = f"{_from[0]} ({_from[1]})" if isinstance(_from, list) else _from
              print(f"  {color}FROM \033[0m{from_str} {color}→ TO \033[0m{to} \033[90m@ {at}\033[0m")
          else:
              print(f"  {color}→ TO \033[0m{to} \033[90m@ {at}\033[0m")

      # Mostrar resultados de SpamAssassin
      print("\n\033[1;34m  🚫   >   SPAMASSASSIN \033[0m")
      print("‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
      spam = report_data["spamassassin"]
      print(f"SpamAssassin version: {general['spamassassin_version']}")
      print(f"Is email spam? {spam['spam_status']}")
      print(f"Score: {spam['score']}")
      print("Tests:")
      for test in spam["tests"]:
        print(f" - {test['name']} ({test['score']}): {test['description']}")

      # Mostrar autenticación DKIM
      print("\n\033[1;34m  🔐   >   AUTHENTICATION \033[0m")
      print("‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾")
      process_authentication("dkim", report_data["authentication"]["dkim"]) 
      process_authentication("spf", report_data["authentication"]["spf"])
      process_authentication("rdns", report_data["authentication"]["rdns"])
      process_authentication("dmarc", report_data["authentication"]["dmarc"])
      process_authentication("domain_mx", report_data["authentication"]["domain_mx"])

      print("\n\033[1;34m  🧱   >   RBL CHECKS \033[0m")
      print("‾" * 40)

      for test in report_data["rbl"]["tests"]:
          result_text = test["result"]
          result = result_text.lower()
          
          # Determinar icono y color según el resultado
          if "not listed" in result:
              icon = "\033[92m[✓]\033[0m"  # Verde
          elif "timeout" in result:
              icon = "\033[93m[~]\033[0m"  # Amarillo
          else:
              icon = "\033[91m[✗]\033[0m"  # Rojo

          print(f"{icon} {test['name']} \033[90m→ {result}\033[0m")

      print(f"\n\033[90m{report_data['rbl']['count']} RBLs checked in {report_data['rbl']['processed_in']}s\033[0m\n")
  except Exception as e:
    print(f"Error: {e}")
  finally:
    connection.close()

def get_domain():
  print(f"Working on it... :)")

def set_domain():
  print(f"Working on it... :)")

def print_help():
  prog = os.path.basename(__file__)
  print(f'''\

 █████ █████                                          
░░███ ░░███                                           
 ░░███ ███              ████████   ██████   █████ ████
  ░░█████    ██████████░░███░░███ ░░░░░███ ░░███ ░███ 
   ███░███  ░░░░░░░░░░  ░███ ░░░   ███████  ░███ ░███ 
  ███ ░░███             ░███      ███░░███  ░███ ░███ 
 █████ █████            █████    ░░████████ ░░███████ 
░░░░░ ░░░░░            ░░░░░      ░░░░░░░░   ░░░░░███ 
                                             ███ ░███ 
                                            ░░██████  
                                             ░░░░░░   

\033[92mA Python project that integrates with Postfix and analyses incoming email to
generate reports that can be used in webapps or other projects.\033[0m

\033[93mGive the repo a star if you like it!\033[0m
\033[96mGitHub\033[0m: https://github.com/ortegavidaljl/x-ray

USAGE:
  {prog} {{create|set|delete|get|check}} {{domain|account|report}} {{name|id}}
    
  {prog} create  domain   <name>
  {prog} create  account
  {prog} set     domain   <name>
  {prog} delete  domain   <name>
  {prog} delete  account  <name@domain.tld>
  {prog} get     domain
  {prog} get     report   <name@domain.tld|id>
  {prog} check   account  <name@domain.tld>
  {prog} check   domain   <name>

EXAMPLES:
  > {prog} \033[92mcreate\033[0m domain name.tld
    -----------------------------
     Create a domain named "name.tld". If this is the first/only domain on the
     DB, it will automatically activated. Otherwise, will be added but disabled.
    
  > {prog} \033[92mcreate\033[0m account
    ---------------------
     Create and output a random account under the active domain. 
    
  > {prog} \033[95mset\033[0m domain name.tld
    --------------------------
     Set domain "name.tld" as active.
    
  > {prog} \033[91mdelete\033[0m domain name.tld
    -----------------------------
     Delete domain "name.tld". Active domains can't be removed.
      
  > {prog} \033[91mdelete\033[0m account name@domain.tld
    --------------------------
     Delete account named "name". It will also delete all its reports.
    
  > {prog} \033[96mget\033[0m domain
    -----------------
     List available domains, showing the active domain first.
    
  > {prog} \033[96mget\033[0m report {{id|name@domain.tld}}
    ----------------------
     - If an account is given, get its latest report. The output will show first
       all the reports available and their generation dates.
     - If an id is given, get the specific report.
    
     \033[91m[!]\033[0m If ENCRYPTION env var is enabled, trying to get a report without
     cryptographic keys generated will result in error. Also, reports encrypted
     using other encryption keys won't be retrievable nor readable.
    
  > {prog} \033[33mcheck\033[0m account name@domain.tld
    -------------------------
     Check if the account "name@domain.tld" exists.
    
  > {prog} \033[33mcheck\033[0m domain name.tld
    -------------------------
     Check if the domain "name.tld" exists.
''')
  exit()

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-h', '--help', action='store_true', help='Mostrar esta ayuda')

subparsers = parser.add_subparsers(dest="action", required=False, help="Acciones disponibles")

# Subcomando: help
help_parser = subparsers.add_parser("help", help="Mostrar esta ayuda")

# Subcomando: create
create_parser = subparsers.add_parser("create", help="Crear un nuevo dominio o cuenta")
create_parser.add_argument("type", choices=["domain", "account"], help="Tipo de entidad a crear")
create_parser.add_argument("-n", "--name", type=str, help="Nombre del dominio (requerido para dominios)")

# Subcomando: delete
delete_parser = subparsers.add_parser("delete", help="Eliminar un dominio o cuenta")
delete_parser.add_argument("type", choices=["domain", "account"], help="Tipo de entidad a eliminar")
delete_parser.add_argument("-n", "--name", type=str, required=True, help="Nombre del dominio o cuenta a eliminar")

# Subcomando: get
get_parser = subparsers.add_parser("get", help="Obtener información de reportes o cuentas")
get_parser.add_argument("type", choices=["report", "domain"], help="Tipo de información a obtener")
get_parser.add_argument("-i", "--id", type=str, help="ID o UUID del reporte")
get_parser.add_argument("-n", "--name", type=str, help="Nombre de la cuenta")

args = parser.parse_args()

if args.help or len(sys.argv) == 1:
  print_help()

if args.action == "help":
  print_help()

elif args.action == "create":
  if args.type == "domain":
    if not args.name:
      print(f"ERROR: Para la acción 'create domain', el argumento -n|--name es requerido.")
      print(f"USAGE: {os.path.basename(__file__)} create domain -n|--name <name.tld>")
      exit(1)
    create_domain()

  elif args.type == "account":
    if args.name:
      # 'create account' no debería llevar el argumento --name según la ayuda.
      print(f"ERROR: La acción 'create account' no utiliza el argumento -n|--name.")
      print(f"USAGE: {os.path.basename(__file__)} create account")
      exit(1)
    create_account()

elif args.action == "delete":
  if args.type == "domain":
    delete_domain()

  elif args.type == "account":
    delete_account()

elif args.action == "get":
  if args.type == "report":
    if not args.id and not args.name:
      print(f"Error: Para la acción 'get report', se requiere el argumento --id o --name.")
      print(f"Uso: {os.path.basename(__file__)} get report --name <nombre_cuenta> O --id <id_reporte>")
      exit(1)
    get_report()

  elif args.type == "domain":
    if not args.name:
      print(f"Error: Para la acción 'get domain', el argumento --name es requerido.")
      exit(1)
    get_domain()

elif args.action == "check":
  if args.type == "account":
    if not args.name:
      print(f"Error: Para la acción 'check account', se requiere el argumento --name.")
      exit(1)
    check_account()

  elif args.type == "domain":
    if not args.name:
      print(f"Error: Para la acción 'get domain', el argumento --name es requerido.")
      exit(1)
    check_domain()

elif args.action == "set":
  if args.type == "domain":
    if not args.name:
      print(f"Error: Para la acción 'set domain', el argumento --name es requerido.")
      exit(1)
    set_domain()