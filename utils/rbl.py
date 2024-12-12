import time
import dns
import dns.resolver
import dns.asyncresolver
import asyncio
from utils.config import log
from utils.scoring import Score

async def check_rbl(ip_address, score):
  start = time.time()
  rbl_list = {
    'SORBS 48h': ['new.spam.dnsbl.sorbs.net', 'http://www.sorbs.net/lookup.shtml'],
    'SORBS 28d': ["recent.spam.dnsbl.sorbs.net", 'http://www.sorbs.net/lookup.shtml'],
    'SPAMCOP': ['bl.spamcop.net', 'https://www.spamcop.net/bl.shtml'],
    'Spamhaus ZEN (SBL, CSS, XBL, BPL)': ['zen.spamhaus.org', 'https://check.spamhaus.org/'],
    'RATS-Spam': ['spam.spamrats.com', 'https://spamrats.com/removal.php'],
    'Barracuda': ['b.barracudacentral.org', 'https://www.barracudacentral.org/lookups'],
    'UCEPROTECT LVL1': ['dnsbl-1.uceprotect.net', 'https://www.uceprotect.net/en/rblcheck.php'],
    'UCEPROTECT LVL2': ['dnsbl-2.uceprotect.net', 'https://www.uceprotect.net/en/rblcheck.php'],
    'UCEPROTECT LVL3': ['dnsbl-3.uceprotect.net', 'https://www.uceprotect.net/en/rblcheck.php'],
    'Backscatterer': ['ips.backscatterer.org', 'https://www.backscatterer.org/?target=test']
  }

  tasks = [check_single_rbl(ip_address, rbl_name, rbl_data) for rbl_name, rbl_data in rbl_list.items()]
  results = await asyncio.gather(*tasks)

  is_ip_listed = any(result['result'] == 'Listed' for result in results)
  check_result = {
    "tests": results,
    "message": "rbl:ok" if not is_ip_listed else "rbl:nok",
    "status": "success" if not is_ip_listed else "warning",
    "count": len(rbl_list),
    "processed_in": time.time() - start
  }

  if is_ip_listed:
    check_result["subtract"] = score.subtract("rbl", Score.RBL_ERR.value)

  log(f"RBL Check finished: {check_result['count']} lists in {check_result['processed_in']} seconds")

  return check_result

async def check_single_rbl(ip_address, rbl_name, rbl_data):
  query = '.'.join(reversed(str(ip_address).split('.'))) + '.' + rbl_data[0]
  exception_to_result = {
      dns.asyncresolver.NXDOMAIN: 'Not listed',
      dns.exception.Timeout: 'Timeout',
      dns.resolver.LifetimeTimeout: 'Timeout',
      dns.asyncresolver.NoAnswer: 'Unknown',
      dns.resolver.NoNameservers: 'NoNS'
  }
  
  try:
      await dns.asyncresolver.resolve(query, 'A')
      result = 'Listed'
  except tuple(exception_to_result.keys()) as e:
      result = exception_to_result[type(e)]

  return {
      "name": rbl_name,
      "url": rbl_data[1],
      "result": result
  }