import re
import subprocess
from decimal import Decimal
from utils.scoring import Score

async def check_rspamd(email, score):
  check_result = {
    "message": "rspamd:ok",
    "status": "success",
    "tests": []
  }

  rspamd_version = subprocess.run(["/usr/bin/rspamadm", "--version"], capture_output=True, text=True)

  check_result['version'] = rspamd_version.stdout.strip().split()[1]

  # --- Análisis de Rspamd ---
  if 'X-Spamd-Result' in email:
    header_value = email['X-Spamd-Result']

    # Extraer estado global
    first_match = re.search(r'default:\s+(True|False)\s+\[([-\d\.]+)\s*/\s*([\d\.]+)\]', header_value, re.IGNORECASE)
    if first_match:
      is_spam = first_match.group(1).lower() == 'true'
      score_val = float(first_match.group(2))
      threshold_val = float(first_match.group(3))

      check_result['is_spam'] = is_spam
      check_result['score'] = score_val
      check_result['threshold'] = threshold_val

      if is_spam:
        check_result['message'] = "rspamd:nok"
        check_result['status'] = "error"
        check_result["subtract"] = score.subtract("rspamd", Score.RSPAMD_SPAM.value)
      else:
        if Decimal(score_val) >= Decimal(5):
          check_result['message'] = "rspamd:shouldReview"
          check_result['status'] = "warning"

    # Extraer reglas individuales
    entries = header_value.split(';')[1:]  # Ignora el primer segmento "default: ..."
    pattern = re.compile(r'(?P<name>[A-Z0-9_]+)(?:\((?P<value>-?\d+\.\d+)\))?(?:\[(?P<info>[^\]]*)\])?', re.IGNORECASE)

    for entry in entries:
      entry = entry.strip().rstrip(';')
      match = pattern.match(entry)
      if match:
        check_result['tests'].append({
          "name": match.group('name'),
          "score": match.group('value'),
          "description": match.group('info') or "",
          "source": "rspamd"
        })

  return check_result

async def check_spamassassin(email, score):

  check_result = {
    "message": "sa:ok",
    "status": "success",
  }

  if 'X-Spam-Checker-Version' in email:
    pattern_version = r"SpamAssassin\s(?P<version>[\d.]+)\s"
    match_version = re.search(pattern_version, email['X-Spam-Checker-Version'])
    check_result['version'] = match_version.group('version')
  else:
    check_result['version'] = "N.A."

  if 'X-Spam-Flag' in email:
    check_result['is_spam'] = email['X-Spam-Flag']

  if 'X-Spam-Score' in email:
    check_result['score'] = email['X-Spam-Score']

  if 'X-Spam-Status' in email:
    check_result['spam_status'] = email['X-Spam-Status']
    if email['X-Spam-Status'] == "YES":
      check_result['message'] = "sa:nok"
      check_result['status'] = "warning"
      check_result["subtract"] = score.subtract("spamassassin", Score.RSPAMD_SPAM.value)
    else:
      if Decimal(3) <= Decimal(email['X-Spam-Score']) <= Decimal(4.99):
        check_result['message'] = "sa:shouldReview"
        check_result['status'] = "warning"

  if 'X-Spam-Report' in email:  
    pattern = re.compile(r'\*\s*(-?\d+\.\d+)\s+(\w+)\s(.*)')
    tests_result = []
    for line in email['X-Spam-Report'].strip().replace("\t", "\n").splitlines():
      match = pattern.match(line)
      if match:
        # Obtener las columnas requeridas
        tests_result.append ({
          "name": match.group(2),
          "score": match.group(1),
          "description": match.group(3)
        })
    
    check_result['tests'] = tests_result

  return check_result