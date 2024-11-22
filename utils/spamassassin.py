import re
from decimal import Decimal
from utils.scoring import Score

async def check_spamassassin(email, score):
  check_result = {
    "message": "sa:ok",
    "status": "success",
  }

  if 'X-Spam-Checker-Version' in email:
    pattern_version = r"SpamAssassin\s(?P<version>[\d.]+)\s"
    match_version = re.search(pattern_version, email['X-Spam-Checker-Version'])
    check_result['version'] = match_version.group('version')

  if 'X-Spam-Flag' in email:
    check_result['is_spam'] = email['X-Spam-Flag']

  if 'X-Spam-Score' in email:
    check_result['score'] = email['X-Spam-Score']

  if 'X-Spam-Status' in email:
    check_result['spam_status'] = email['X-Spam-Status']
    if email['X-Spam-Status'] == "YES":
      check_result['message'] = "sa:nok"
      check_result['status'] = "warning"
      check_result["subtract"] = score.subtract("spamassassin", Score.SPAMASSASSIN_SPAM.value)
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