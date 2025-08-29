import time
import dns
import dns.resolver
import dns.asyncresolver
import asyncio
from utils.config import log
from utils.scoring import Score

resolver = dns.asyncresolver.Resolver()
resolver.lifetime = 1.5
resolver.timeout = 1.0

RBL_LIST = {
  'SORBS 48h': ['new.spam.dnsbl.sorbs.net', 'http://www.sorbs.net/lookup.shtml'],
  'SORBS 28d': ["recent.spam.dnsbl.sorbs.net", 'http://www.sorbs.net/lookup.shtml'],
  'SPAMCOP': ['bl.spamcop.net', 'https://www.spamcop.net/bl.shtml'],
  'Spamhaus ZEN (SBL, CSS, XBL, BPL)': ['zen.spamhaus.org', 'https://check.spamhaus.org/'],
  'RATS-Spam': ['spam.spamrats.com', 'https://spamrats.com/removal.php'],
  'Barracuda': ['b.barracudacentral.org', 'https://www.barracudacentral.org/lookups'],
  'UCEPROTECT LVL1': ['dnsbl-1.uceprotect.net', 'https://www.uceprotect.net/en/rblcheck.php'],
  'UCEPROTECT LVL2': ['dnsbl-2.uceprotect.net', 'https://www.uceprotect.net/en/rblcheck.php'],
  'UCEPROTECT LVL3': ['dnsbl-3.uceprotect.net', 'https://www.uceprotect.net/en/rblcheck.php'],
  'Backscatterer': ['ips.backscatterer.org', 'https://www.backscatterer.org/?target=test'],
  'DRONEBL': ['dnsbl.dronebl.org', 'https://www.dronebl.org/lookup'],
  'Usenix s5h.net': ['all.s5h.net', 'https://www.usenix.org.uk/content/rbl.html'],
}

async def check_rbl(ip_address, score):
  start = time.time()

  tasks = [check_single_rbl(ip_address, rbl_name, rbl_data) for rbl_name, rbl_data in RBL_LIST.items()]
  results = await asyncio.gather(*tasks)

  is_ip_listed = any(result['result'] == 'Listed' for result in results)
  
  check_result = {
    "tests": results,
    "status": "success" if not is_ip_listed else "warning",
    "count": len(RBL_LIST),
    "processed_in": round(time.time() - start, 3)
  }

  if is_ip_listed:
    check_result["subtract"] = score.subtract("rbl", Score.RBL_ERR.value)

  return check_result

async def check_single_rbl(ip_address, rbl_name, rbl_data):
  query = '.'.join(reversed(str(ip_address).split('.'))) + '.' + rbl_data[0]
  
  try:
    await resolver.resolve(query, 'A')
    result = 'Listed'
  except dns.resolver.NXDOMAIN:
    result = 'Not listed'
  except (dns.exception.Timeout, dns.resolver.LifetimeTimeout):
    result = 'Timeout'
  except dns.asyncresolver.NoAnswer:
    result = 'Unknown'
  except dns.resolver.NoNameservers:
    result = 'NoNS'
  except Exception as e:
    result = f"Error: {e}"

  return {
    "name": rbl_name,
    "url": rbl_data[1],
    "result": result
  }