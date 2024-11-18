import subprocess
import re
import dns
import dns.resolver
import dns.asyncresolver
import dkim
import socket
from utils.scoring import Score

async def check_authentication(mail_from, data, received_msg, ip, helo, score):
  rdns = socket.gethostbyaddr(ip)
  domain = mail_from.split("@")[-1]
  
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
    "message": spf_results.get(query_result.returncode, "Unexpected result") ,
    "status": "success",
    "tests": [],
  }

  verify_result['tests'].append({
    "name": "spfquery",
    "result": query_result.stdout
  })

  if query_result.returncode == 1 or query_result.returncode == 2:
    verify_result["status"] = "error"
    verify_result["subtract"] = score.subtract("spf", Score.SPF_ERR)
  elif query_result.returncode == 3:
    verify_result["status"] = "warning"
  elif query_result.returncode > 0:
    verify_result["status"] = "warning"
    verify_result["subtract"] = score.subtract("spf", Score.SPF_WARN)

  spf_check = {
    'name': "dns",
    'result' : []
  }

  try:
    spf_dns_result = await dns.asyncresolver.resolve(mail_from.split("@")[-1], 'TXT')
    spf_count = 0
    for rdata in spf_dns_result:
      if rdata.strings[0].startswith(b'v=spf1'):
        spf_check['result'].append(rdata.strings[0].decode("utf-8"))
        spf_count += 1
      if spf_count >= 2:
        verify_result["message"] = "spf:moreThanOne"
        verify_result["status"] = "error"
        verify_result["subtract"] = score.subtract("spf", Score.SPF_ERR)
  except dns.asyncresolver.NoAnswer as e:
    spf_check['result'] = "The DNS does not contain an answer"
  except dns.resolver.NoNameservers as e:
    spf_check['result'] = "All nameservers failed to answer the query"
  except dns.asyncresolver.NXDOMAIN as e:
    spf_check['result'] = "Domain doesn't have an SPF record"

  verify_result['tests'].append(spf_check)

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
    verify_result["subtract"] = score.subtract("rdns", Score.RDNS_WARN)

  return verify_result

async def verify_dmarc(domain):
  verify_result = {
    "message": "dmarc:nok",
    "status": "warning",
    "tests": []
  }

  record = "_dmarc." + domain
  dns_test =  {
    'name': "dns",
    'result' : []
  }

  try:
    dmarc_dns_result = await dns.asyncresolver.resolve("_dmarc." + domain, 'TXT')
    for rdata in dmarc_dns_result:
      verify_result['message'] = "dmarc:ok"
      verify_result['status'] = "success"
      dns_test['result'].append(rdata.strings[0].decode("utf-8"))
  except dns.asyncresolver.NoAnswer as e:
    dns_test['result'].append(f"DMARC record {record} was not found on domain's zone")
  except dns.resolver.NoNameservers as e:
    dns_test['result'].append("All nameservers failed to answer the query")
    verify_result['status'] = "error"
  except dns.asyncresolver.NXDOMAIN as e:
    dns_test['result'].append("Domain doesn't have a DMARC record")
    verify_result['status'] = "error"

  verify_result['tests'].append(dns_test)

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

  try:
    mx_dns_result = await dns.asyncresolver.resolve(domain, 'MX')
    verify_result['message'] = "domain_mx:ok"
    verify_result['status'] = "success"
    for rdata in mx_dns_result:
      mx_check['result'].append([rdata.preference, rdata.exchange.to_unicode()])
  except dns.asyncresolver.NoAnswer as e:
    verify_result['mx'] = "Domain doesn't have MX records"
    verify_result["subtract"] = score.subtract("mx", Score.MX_WARN)
  except dns.resolver.NoNameservers as e:
    verify_result['status'] = "error"
    verify_result['mx'] = "All nameservers failed to answer the query"
    verify_result["subtract"] = score.subtract("mx", Score.MX_WARN)
  except dns.asyncresolver.NXDOMAIN as e:
    verify_result['status'] = "error"
    verify_result['mx'] = "Domain doesn't have MX records"
    verify_result["subtract"] = score.subtract("mx", Score.MX_WARN)

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
    verify_result["subtract"] = score.subtract("dkim", Score.DKIM_NO)
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
    verify_result["subtract"] = score.subtract("dkim", Score.DKIM_ERR)

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

  record = dkim_selector + "._domainkey." + domain
  dns_test =  {
    'name': "dns",
    'result' : []
  }

  try:
    dkim_dns_result = await dns.asyncresolver.resolve(record, 'TXT')
    for rdata in dkim_dns_result:
      dns_test['result'].append(rdata.strings[0].decode("utf-8"))
  except dns.asyncresolver.NoAnswer as e:
    dns_test['result'].append(f"DMARC record {record} was not found on domain's zone")
  except dns.resolver.NoNameservers as e:
    dns_test['result'].append("All nameservers failed to answer the query")
  except dns.asyncresolver.NXDOMAIN as e:
    dns_test['result'].append("Domain doesn't have a DKIM record")

  verify_result['tests'].append(dns_test)
  
  return verify_result

async def verify_arc(email):
  verify_result = {
    "message": "arc:nok",
    "status": "error",
    "tests": []
  }

  try:
    cv, res, reason = dkim.arc_verify(email)

    if cv == 'fail':
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": reason
      })
    elif cv == 'pass':
      verify_result['message'] = "arc:ok"
      verify_result['status'] = "success"
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": reason
      })
    else:
      verify_result['message'] = "arc:notSigned"
      verify_result['status'] = "success"
      verify_result['tests'].append({
        "name": 'dkimpy',
        "result": reason
      })
  except dkim.DKIMException as e:
    verify_result['tests'].append({
        "name": 'dkimpy',
        "result": f"Error validating ARC chain {e}"
      })
  
  return verify_result