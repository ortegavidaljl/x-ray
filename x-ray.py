#!/usr/bin/python3.11

from aiosmtpd.controller import Controller

import time
from utils.config import log, check_db, VERSION, PORT, HOSTNAME
from utils.report import generate_reports
from utils.database import save_report

class CustomHandler:
  async def handle_DATA(self, server, session, envelope):

    log(f"Processing message from {envelope.mail_from}")

    #helo = session.host_name
    
    # Remove in production, we don't need the email to actually be delivered
    #with SMTPClient('127.0.0.1', port=10032) as server:
    #  server.sendmail(mail_from, rcpt_tos, data)
    #  server.quit()

    #ip = socket.gethostbyname(email_trace[-2]['from'][0])

    general_report, spamassassin_report, authentication_report, rbl_report = await generate_reports(envelope)
    
    await save_report(general_report['sent_to'], general_report, spamassassin_report, authentication_report, rbl_report)

    return '250 OK'

if __name__ == '__main__':
  check_db()
  log(f"Requirements and config checked; Starting...")

  handler = CustomHandler()
  controller = Controller(handler, hostname=HOSTNAME, port=PORT)
  log(f"Service started on {HOSTNAME}:{PORT}, version {VERSION}.")
  # Run the event loop in a separate thread.
  controller.start()

  while True:
    time.sleep(10)