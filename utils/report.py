import re
import asyncio
from decimal import Decimal
import time
import email
from email import policy
from utils.config import VERSION

import datetime

from utils.rbl import check_rbl
from utils.spam import check_rspamd, check_spamassassin
from utils.extras import check_extras
from utils.authentication import check_authentication
from utils.scoring import EmailScore

async def generate_report(envelope):
  start_proc_time = time.time()

  score = EmailScore()
  mail_from = envelope.mail_from
  rcpt_tos = envelope.rcpt_tos
  data = envelope.content
  received_msg = email.message_from_bytes(data, policy=email.policy.SMTP)

  email_trace = get_trace1(received_msg)

  if not email_trace:
    raise Exception("The email trace shouldn't be empty. This might indicate that the message was sent directly to this service.")
  
  for item in email_trace:
    if 'from' in item:
      sender = item['from']
      break
        
  helo = sender[0]
  ip = sender[1]

  # Ejecutar tareas en paralelo
  rspamd_task = asyncio.create_task(check_rspamd(received_msg, score))
  #clamav_task = asyncio.create_task(check_clamav(received_msg, score))
  #spamd_task = asyncio.create_task(check_spamassassin(received_msg, score))
  auth_task = asyncio.create_task(check_authentication(mail_from, data, received_msg, ip, helo, score))
  extras_task = asyncio.create_task(check_extras(mail_from, data, received_msg, ip, helo, score))
  rbl_task = asyncio.create_task(check_rbl(ip, score))

  # Esperar resultados
  rspamd_report, extras_report, authentication_report, rbl_report = await asyncio.gather(rspamd_task, extras_task, auth_task, rbl_task)

  general_report = {
    "status": "info",
    "message_date": datetime.datetime.strptime(received_msg['Date'], '%a, %d %b %Y %H:%M:%S %z').strftime('%d-%m-%Y %H:%M:%S'),
    "header": get_header(score),
    "score": score.email_score,
    "score_breakdown": score.email_score_breakdown,
    "max_score": 10,
    "source_ip": ip,
    "source_helo": helo,
    "sent_from": mail_from,
    "sent_to": rcpt_tos[0],
    "processed_in": time.time() - start_proc_time,
    "rbl_processed_in": rbl_report['processed_in'],
    "tester_version": VERSION,
    "complete_message": envelope.content.decode('utf8', errors='replace'),
    #"trace": email_trace
  }

  return {
    "general": general_report,
    "spam": rspamd_report,
    "extras": extras_report,
    "authentication": authentication_report,
    "rbl": rbl_report
  }


def get_header(score):
  if Decimal(0) <= Decimal(score.email_score) <= Decimal(3.99):
    return "Your message may never be delivered"
  elif Decimal(4) <= Decimal(score.email_score) <= Decimal(5.99):
    return "Your message may be discarded"
  elif Decimal(6) <= Decimal(score.email_score) <= Decimal(7.99):
    return "Your message may experience delivery problems"
  elif Decimal(8) <= Decimal(score.email_score) <= Decimal(10.99):
    return "Your message passed all tests and should be delivered"
  else:
    return f"Uhmm... Something unexpected happened"
  
def get_trace(email):
  received_headers = list(email.get_all('Received') or [])
  received_headers.reverse()  # Del primer al último hop

  trace = []
  server_ip_map = {}

  
  for header in received_headers:
      line = ' '.join(header.splitlines())
      from_match = re.search(r'from\s+([^\s(]+).*?\[([0-9a-fA-F:.]+)\]', line)
      if from_match:
          server_name = from_match.group(1)
          ip = from_match.group(2)
          if server_name not in server_ip_map:
              server_ip_map[server_name] = ip

  
  for i, header in enumerate(received_headers):
      hop = {
          'hop': i + 1,
          'server': None,
          'ip': None,
          'time': None
      }

      line = ' '.join(header.splitlines())

      # Extraer la fecha
      time_match = re.search(r';\s*(.+)$', line)
      if time_match:
          hop['time'] = time_match.group(1).strip()

      # Extraer servidor que recibe (BY)
      by_match = re.search(r'\bby\s+([^\s(]+)', line, re.IGNORECASE)
      if by_match:
          server = by_match.group(1)
          hop['server'] = server
          hop['ip'] = server_ip_map.get(server)
      else:
          hop['server'] = '?'

      trace.append(hop)

  return trace

def get_trace_lele(email):
  received_headers = list(email.get_all('Received') or [])
  received_headers.reverse()

  trace = []
  for i, header in enumerate(received_headers):
      hop = {'hop': i + 1, 'from': None, 'to': None, 'ip': None, 'time': None}

      line = ' '.join(header.splitlines())

      # Extraer fecha
      time_match = re.search(r';\s*(.+)$', line)
      if time_match:
          hop['time'] = time_match.group(1).strip()
          line = re.sub(r';\s*.+$', '', line)

      # IP (mejor soporte IPv6)
      ip_match = re.search(r'\[([0-9a-fA-F:.]+)\]', line)
      if ip_match:
          hop['ip'] = ip_match.group(1)

      # Extraer from y by
      from_by_match = re.search(r'\bfrom\s+([^\s(]+).*?\bby\s+([^\s(]+)', line, re.IGNORECASE)
      if from_by_match:
          hop['from'] = from_by_match.group(1).lower()
          hop['to'] = from_by_match.group(2).lower()
      else:
          by_match = re.search(r'\bby\s+([^\s(]+)', line, re.IGNORECASE)
          from_match = re.search(r'\bfrom\s+([^\s(]+)', line, re.IGNORECASE)

          if by_match:
              hop['from'] = 'local'
              hop['to'] = by_match.group(1).lower()
          elif from_match:
              hop['from'] = from_match.group(1).lower()
              hop['to'] = '?'
          else:
              hop['from'] = '?'
              hop['to'] = '?'

      trace.append(hop)

  return trace

def get_trace2(email):
    received_headers = list(email.get_all('Received') or [])
    received_headers.reverse()  # Orden cronológico: origen al destino final

    trace = []
    for i, header in enumerate(received_headers):
        hop = {'hop': i + 1, 'from': None, 'to': None, 'ip': None, 'time': None}

        # Unificar en una sola línea para facilitar el parsing
        line = ' '.join(header.splitlines())
        
        # Extraer fecha (lo que sigue al último punto y coma)
        time_match = re.search(r';\s*(.+)$', line)
        if time_match:
            hop['time'] = time_match.group(1).strip()
            line = re.sub(r';\s*.+$', '', line)  # eliminar timestamp del texto a analizar

        # Extraer IP entre corchetes
        ip_match = re.search(r'\[([^\]]+)\]', line)
        if ip_match:
            hop['ip'] = ip_match.group(1)

        # Extraer dominios "from ... by ..."
        from_by_match = re.search(r'from\s+([^\s(]+).*?by\s+([^\s(]+)', line, re.IGNORECASE)
        if from_by_match:
            hop['from'] = from_by_match.group(1)
            hop['to'] = from_by_match.group(2)

        # Solo "by"
        elif re.search(r'\bby\s+([^\s(]+)', line, re.IGNORECASE):
            hop['from'] = 'local'
            hop['to'] = re.search(r'\bby\s+([^\s(]+)', line, re.IGNORECASE).group(1)

        # Solo "from"
        elif re.search(r'\bfrom\s+([^\s(]+)', line, re.IGNORECASE):
            hop['from'] = re.search(r'\bfrom\s+([^\s(]+)', line, re.IGNORECASE).group(1)
            hop['to'] = '?'

        else:
            hop['from'] = '?'
            hop['to'] = '?'

        trace.append(hop)

    return trace

def get_trace1(email):
  received_headers = list(email.get_all('Received') or []) #list(reversed(email.get_all('Received')))
  
  trace = []

  pattern_from = r"from\s+(?P<sender_name>[^()]+)\s+\(([^()]+)\s+\[(?P<sender_ip>[^\]]+)\]\)\s+(\(.*\)\s)?(by)?\s+(?P<recipient_name>[^()]+)\s+.*;\s+(?P<timestamp>.*)"
  pattern_by = r"by\s+(?P<sender_name>[\S]+)\s*(with)?\s+.*;\s+(?P<timestamp>.+)"

  for header in list(received_headers):
    match_from = re.search(pattern_from, header)
    match_by = re.search(pattern_by, header)
    if match_from:
      trace.append({
        "from": [match_from.group('sender_name'), match_from.group('sender_ip')],
        "to": match_from.group('recipient_name'),
        "at": match_from.group('timestamp')
      })
    elif match_by:
      trace.append({
        "to": match_by.group('sender_name'),
        "at": match_by.group('timestamp')
      })
  
  return trace