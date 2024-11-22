import re
import asyncio
from decimal import Decimal
import time
import email
from email import policy
from utils.config import VERSION

import datetime

from utils.rbl import check_rbl
from utils.spamassassin import check_spamassassin
from utils.authentication import check_authentication
from utils.scoring import EmailScore

async def generate_reports(envelope):
  start_proc_time = time.time()

  score = EmailScore()
  mail_from = envelope.mail_from
  rcpt_tos = envelope.rcpt_tos
  data = envelope.content
  received_msg = email.message_from_bytes(data, policy=email.policy.SMTP)

  email_trace = get_trace(received_msg)
  
  for item in email_trace:
    if 'from' in item:
      sender = item['from']
      break
        
  helo = sender[0]
  ip = sender[1]

  # Ejecutar tareas en paralelo
  spam_task = asyncio.create_task(check_spamassassin(received_msg, score))
  auth_task = asyncio.create_task(check_authentication(mail_from, data, received_msg, ip, helo, score))
  rbl_task = asyncio.create_task(check_rbl(ip, score))

  # Esperar resultados
  spamassassin_report, authentication_report, rbl_report = await asyncio.gather(spam_task, auth_task, rbl_task)

  general_report = {
    "message": "message:info",
    "message_date": datetime.datetime.strptime(received_msg['Date'], '%a, %d %b %Y %H:%M:%S %z').strftime('%d-%m-%Y %H:%M:%S'),
    "header": get_header(score),
    "score": score.email_score,
    "score_breakdown": score.email_score_breakdown,
    "max_score": 10,
    "source_ip": ip,
    "source_helo": helo,
    "sent_from": mail_from,
    "sent_to": rcpt_tos[0],
    "processed_in": (time.time() - start_proc_time) + rbl_report['processed_in'],
    "spamassassin_version": spamassassin_report['version'],
    "tester_version": VERSION,
    "complete_message": envelope.content.decode('utf8', errors='replace'),
    "trace": email_trace
  }

  return general_report, spamassassin_report, authentication_report, rbl_report


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
  received_headers = list(reversed(email.get_all('Received')))
  trace = []

  pattern_from = r"from\s+(?P<sender_name>[^()]+)\s+\(([^()]+)\s+\[(?P<sender_ip>[^\]]+)\]\)\s+(\(.*\)\s)?(by)?\s+(?P<recipient_name>[^()]+)\s+.*;\s+(?P<timestamp>.*)"
  pattern_by = r"by\s+(?P<sender_name>[\S]+)\s*(with)?\s+.*;\s+(?P<timestamp>.+)"

  for header in received_headers:
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