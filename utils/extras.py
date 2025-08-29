import subprocess
import re
import dkim
import socket
from utils.scoring import Score
from utils.misc import DNS

async def check_extras(mail_from, data, received_msg, ip, helo, score):
  
  return {
    "antivirus": await check_clamav(received_msg, score),
    "unsubscribe": await check_unsubscribe_header(received_msg)
  }

async def check_clamav(email, score):
  verify_result = {
    "status": "success",
    "version": None,
    "tests": {}
  }

  clamav_version = subprocess.run(
    ["/usr/sbin/clamd", "--version"],
    capture_output=True,
    text=True
  )
  verify_result['version'] = clamav_version.stdout.partition(" ")[2].strip()

  if 'X-Spamd-Result' in email:
    header_value = email['X-Spamd-Result']

    match = re.search(r'CLAM_VIRUS\([-\d\.]+\)\[([^\]]+)\]', header_value, re.IGNORECASE)
    if match:
      verify_result["subtract"] = score.subtract("clamav", Score.CLAMAV_VIRUS.value)
      verify_result['status'] = "error"

      verify_result['tests']["clamscan"] = {
        "result": f"malware found: {match.group(1)}"
      }
    else:
      verify_result['tests']["clamscan"] = {
        "result": "clean message"
      }

  return verify_result

async def check_unsubscribe_header(email):
  verify_result = {
    "status": "success",
    "tests": {}
  }

  if "List-Unsubscribe" not in email:
    verify_result["tests"]["header"] = {
      "result": "No List-Unsubscribe header found"
    }
    verify_result["status"] = "info"
    return verify_result

  header_value = email["List-Unsubscribe"]
  match = re.search(r"<([^>]+)>", header_value, re.IGNORECASE)

  if not match:
    verify_result["tests"]["header"] = {
      "result": f"Invalid List-Unsubscribe format: {header_value}"
    }
    verify_result["status"] = "error"
    return verify_result

  verify_result["tests"]["header"] = {
    "result": header_value
  }

  if "List-Unsubscribe-Post" in email:
    post_value = email["List-Unsubscribe-Post"]
    verify_result["tests"]["post"] = {
      "result": post_value
    }

  return verify_result