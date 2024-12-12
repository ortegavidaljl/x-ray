import subprocess
import re
import dkim
import socket
from utils.scoring import Score
from utils.misc import DNS

async def check_authentication(mail_from, data, received_msg, ip, helo, score):
  domain = mail_from.split("@")[-1]

  try:
    rdns = socket.gethostbyaddr(ip)
  except socket.error:
    rdns = "none"
  
  return {
    "message": "auth:info",
    "dkim": await verify_dkim(domain, data, received_msg, score),
    "arc": await verify_arc(data),
    "spf": await verify_spf(mail_from, ip, helo, score),
    "rdns": await verify_rdns(ip, helo, rdns[0], score),
    "dmarc": await verify_dmarc(domain),
    "domain_mx": await verify_domain_mx(domain, score),
  }


async def verify_spf(mail_from, ip_address, helo, score):
  query_result = subprocess.run(["spfquery", "--scope", "mfrom", "--id", mail_from, "--ip", ip_address, "--helo-id", helo], capture_output=True, text=True)
  spf_results = {
    0: "spf:ok",
    1: "spf:notAuthorized",
    2: "spf:notAuthorizedOk",
    3: "spf:notSpecified",
    4: "spf:syntaxError",
    5: "spf:dnsError",
    6: "spf:noSPF",
  }

  verify_result = {
    "output": query_result.returncode,
    "message": spf_results.get(query_result.returncode, "spf:unexpectedResult") ,
    "status": "success",
    "tests": [],
  }

  verify_result['tests'].append({
    "name": "spfquery",
    "result": query_result.stdout
  })

  if query_result.returncode == 1 or query_result.returncode == 2:
    verify_result["status"] = "error"
    verify_result["subtract"] = score.subtract("spf", Score.SPF_ERR.value)
  elif query_result.returncode == 3:
    verify_result["status"] = "warning"
  elif query_result.returncode > 0:
    verify_result["status"] = "warning"
    verify_result["subtract"] = score.subtract("spf", Score.SPF_WARN.value)

  dns_test = {
    'name': "dns",
    'result' : []
  }

  dns_query_result = await DNS.resolve(mail_from.split("@")[-1],'TXT', 'spf')

  if dns_query_result["status"] != "success":
    dns_test['result'] = dns_query_result["message"]
    verify_result['tests'].append(dns_test)
    return verify_result
  
  spf_count = 0
  
  for rdata in dns_query_result["data"]:
    if rdata.strings[0].startswith(b'v=spf1'):
      dns_test['result'].append(rdata.strings[0].decode("utf-8"))
      spf_count += 1
    if spf_count >= 2:
      verify_result["message"] = "spf:moreThanOne"
      verify_result["status"] = "error"
      verify_result["subtract"] = score.subtract("spf", Score.SPF_ERR.value)

  verify_result['tests'].append(dns_test)

  return verify_result

async def verify_rdns(ip, helo, rdns, score):
  verify_result = {
    "message": "rdns:ok",
    "status": "success",
    "tests" : [{
      'name': "dns",
      'result' : [
        ['IP:', ip],
        ['HELO:', helo],
        ['rDNS:', rdns]
      ]
    }]
  }

  if helo != rdns:
    verify_result["message"] = "rdns:nok"
    verify_result["status"] = "warning"
    verify_result["subtract"] = score.subtract("rdns", Score.RDNS_WARN.value)

  return verify_result

async def verify_dmarc(domain):
  verify_result = {
    "message": "dmarc:nok",
    "status": "warning",
    "tests": []
  }

  dns_test =  {
    'name': "dns",
    'result' : []
  }

  dmarc_dns_result = await DNS.resolve("_dmarc." + domain, 'TXT', "dmarc")

  if dmarc_dns_result["status"] != "success":
    dns_test['result'] = dmarc_dns_result["message"]
    verify_result['status'] = "error"
    verify_result['tests'].append(dns_test)
    return verify_result
  
  for rdata in dmarc_dns_result["data"]:
    verify_result['message'] = "dmarc:ok"
    verify_result['status'] = "success"
    dns_test['result'].append(rdata.strings[0].decode("utf-8"))

  return verify_result

async def verify_domain_mx(domain, score):
  verify_result = {
    "message": "domain_mx:nok",
    "domain": domain,
    "status": "warning",
    "tests": []
  }

  mx_check = {
    'name': "dns",
    'result' : []
  }

  mx_dns_result = await DNS.resolve(domain, 'MX', 'mx')

  if mx_dns_result["status"] != "success":
    mx_check['result'] = mx_dns_result["message"] 
    verify_result['status'] = "error"
    verify_result["subtract"] = score.subtract("mx", Score.MX_WARN.value)

    verify_result['tests'].append(mx_check)
    return verify_result
  
  verify_result['message'] = "domain_mx:ok"
  verify_result['status'] = "success"
  
  for rdata in mx_dns_result["data"]:
    mx_check['result'].append([rdata.preference, rdata.exchange.to_unicode()])

  verify_result['tests'].append(mx_check)

  return verify_result

async def verify_dkim(domain, email, email_str, score):
  bad_dkim = False
  verify_result = {
    "message": "dkim:ok",
    "status": "success",
    "tests": []
  }

  if not 'DKIM-Signature' in email_str:
    verify_result['message'] = "dkim:notSigned"
    verify_result['status'] = "warning"
    verify_result['tests'].append({
      "name": 'dkimpy',
      "result": 'No DKIM-Signature header present'
    })
    verify_result["subtract"] = score.subtract("dkim", Score.DKIM_NO.value)
    return verify_result
  
  try:
    if dkim.verify(email) == True:
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": 'Message passed DKIM validation'
      })
    else:
      bad_dkim = True
  except dkim.DKIMException as e:
    bad_dkim = True

  if bad_dkim:
    verify_result['message'] = "dkim:nok"
    verify_result['status'] = "error"
    verify_result['tests'].append({
      "name": 'dkimpy',
      "result": 'Message did not pass DKIM validation'
    })
    verify_result["subtract"] = score.subtract("dkim", Score.DKIM_ERR.value)

  pattern_dkim = r"v=((?P<version>[^;]+))|a=((?P<algorithm>[^;]+))|c=((?P<canonicalization>[^;]+))|d=((?P<domain>[^;]+))|s=((?P<selector>[^;]+))|t=((?P<timestamp>[^;]+))|bh=((?P<body_hash>[^;]+))|h=((?P<signed_headers>[^;]+))|b=((?P<signature>[^;]+))"
  
  match_dkim = re.finditer(pattern_dkim, re.sub(r"\s+", "", email_str['DKIM-Signature']))
  header_result={}
  dkim_selector = ""

  if not match_dkim:
    return verify_result
  
  for result in match_dkim:
    for name, value in result.groupdict().items():
      if value is not None:
        header_result[name] = value
        if name == "selector":
          dkim_selector = value

  verify_result['tests'].append({
    "name": 'header',
    "result": header_result
  })

  dns_test =  {
    'name': "dns",
    'result' : []
  }

  dkim_dns_result = await DNS.resolve(dkim_selector + "._domainkey." + domain, 'TXT', 'dkim')

  if dkim_dns_result["status"] != "success":
    dns_test['result'].append(dkim_dns_result["message"])

    verify_result['tests'].append(dns_test)
    return verify_result
 
  for rdata in dkim_dns_result["data"]:
    dns_test['result'].append(rdata.strings[0].decode("utf-8"))

  verify_result['tests'].append(dns_test)
  
  return verify_result

async def verify_arc(email):
  verify_result = {
    "message": "arc:nok",
    "status": "error",
    "tests": []
  }

  #TODO: this doesn't seem to work...
  try:
    cv, res, reason = dkim.arc_verify(email)

    if isinstance(cv, bytes):
      cv = cv.decode('utf-8')
    if isinstance(reason, bytes):
      reason = reason.decode('utf-8')

    if cv == 'fail':
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": reason or "ARC validation failed"
      })
    elif cv == 'pass':
      verify_result['message'] = "arc:ok"
      verify_result['status'] = "success"
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": reason or "ARC validation failed"
      })
    elif cv == 'none':
      verify_result['message'] = "arc:notSigned"
      verify_result['status'] = "warning"
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": "No ARC signature found"
      })
    else:
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": f"Unexpected cv value: {cv}"
      })
  except dkim.DKIMException as e:
    verify_result['tests'].append({
        "name": 'dkimpy',
        "result": f"Error validating ARC chain {e}"
      })
  except Exception as e:
    verify_result['tests'].append({
        "name": 'dkimpy',
        "result": f"Unexpected error: {e}"
    })
  
  return verify_result