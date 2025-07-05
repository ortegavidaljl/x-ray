#!/app/venv/bin/python

from aiosmtpd.controller import Controller

import signal
import time
import sys
from utils.config import log, check_db, VERSION, PORT, HOST
from utils.report import generate_report
from utils.database import save_report

running = True

def signal_handler(sig, frame):
  global running
  running = False
  log("Exit requested by signal.")

signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # kill o system stop

class CustomHandler:
  async def handle_DATA(self, server, session, envelope):

    log(f"Processing message from {envelope.mail_from}")
    
    try:
      await save_report(await generate_report(envelope))
      return '250 OK'
    except Exception as e:
      log(f"Message could not be processed: {e}", "error")
      return '451 Temporary processing error'

if __name__ == '__main__':
  check_db()
  log(f"Requirements and config checked; Starting...")

  handler = CustomHandler()
  controller = Controller(handler, hostname=HOST, port=PORT)
  log(f"Service started on {HOST}:{PORT}, version {VERSION}.")
  # Run the event loop in a separate thread.
  controller.start()

  try:
    while running:
      time.sleep(1)
  finally:
    controller.stop()
    log("Service stopped.")
    sys.exit(0)