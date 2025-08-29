import subprocess
import re
import dkim
import socket
from utils.scoring import Score
from utils.misc import DNS
from checkdmarc import dmarc, spf

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
    "spf": await verify_spf(domain, mail_from, ip, helo, score),
    "rdns": await verify_rdns(ip, helo, rdns[0], score),
    "dmarc": await verify_dmarc(domain, received_msg),
    "domain_mx": await verify_domain_mx(domain, score),
  }

async def verify_spf(domain, mail_from, ip_address, helo, score):
  verify_result = {
    "status": "success",
    "tests": {}
  }

  error_message = None

  try:
    spf_report = spf.get_spf_record(domain)
  except Exception as e:
    error_message = getattr(e, "msg", str(e))
  finally:
    if error_message:
      verify_result["status"] = "error"
      # CHECKDMARC TEST IN CASE OF ERROR
      verify_result["tests"]["checkdmarc"] = {
        "result": error_message
      }
      return verify_result

  # DNS TEST
  verify_result["tests"]["dns"] = {
    "result": spf_report["record"]
  }

  query_result = subprocess.run(
    ["spfquery", "--scope", "mfrom", "--id", mail_from, "--ip", ip_address, "--helo-id", helo],
    capture_output=True,
    text=True
  )

  spf_results = {
    0: "ok",
    1: "not_authorized",
    2: "not_authorized_soft",
    3: "neutral",
    4: "permanent_error",
    5: "temporal_error",
    6: "no_record",
  }

  # SPFQUERY TEST
  verify_result["tests"]["spfquery"] = {
    "output": spf_results.get(query_result.returncode, "unexpected"),
    "result": query_result.stdout
  }

  if query_result.returncode in (1, 2):
    verify_result["status"] = "error"
    verify_result["subtract"] = score.subtract("spf", Score.SPF_ERR.value)
  elif query_result.returncode == 3:
    verify_result["status"] = "warning"
  elif query_result.returncode > 0:
    verify_result["status"] = "warning"
    verify_result["subtract"] = score.subtract("spf", Score.SPF_WARN.value)

  # aux function for spf parsing
  def parse_spf(node, parent=None):
    result = []

    entry = {
      "domain": node.get("domain"),
      "record": node.get("record"),
      "dns_lookups": node.get("dns_lookups", 0),
      "dns_void_lookups": node.get("dns_void_lookups", 0),
      "include_domains": [],
      "parent": parent
    }

    parsed = node.get("parsed", {}) or {}
    includes = parsed.get("include", [])

    for inc in includes:
      entry["include_domains"].append(inc.get("domain"))

    result.append(entry)

    for inc in includes:
      result.extend(parse_spf(inc, parent=node.get("domain")))

    redirect = parsed.get("redirect")
    if redirect:
      result.extend(parse_spf(redirect, parent=node.get("domain")))

    return result

  # CHECKDMARC TEST
  verify_result["tests"]["checkdmarc"] = {
    "result": parse_spf(spf_report)
  }

  return verify_result

async def verify_rdns(ip, helo, rdns, score):
  verify_result = {
    "status": "success",
    "tests" : {}
  }

  # DNS TEST
  verify_result["tests"]["dns"] = {
    "result": [
      ["IP", ip],
      ["HELO", helo],
      ["rDNS", rdns]
    ]
  }

  if helo != rdns:
    verify_result["status"] = "warning"
    verify_result["subtract"] = score.subtract("rdns", Score.RDNS_WARN.value)

  return verify_result

async def verify_dmarc(domain, email_str):
  verify_result = {
    "status": "success",
    "tests": {}
  }

  try:
    dmarc_report = dmarc.get_dmarc_record(domain)
  except (dmarc.DMARCRecordNotFound, dmarc.MultipleDMARCRecords,
          dmarc.UnrelatedTXTRecordFoundAtDMARC) as e:
    verify_result["status"] = "warning"
    verify_result["tests"]["dns"] = {
      "result": getattr(e, 'msg', str(e))
    }
  except Exception as e:
    verify_result["status"] = "error"
    verify_result["subtract"] = score.subtract("dmarc", Score.DMARC_ERR.value)
    verify_result["tests"]["dns"] = {
      "result": getattr(e, 'msg', str(e))
    }
  finally:
    if verify_result["status"] != "success":
      return verify_result

  # DNS TEST
  verify_result["tests"]["dns"] = {
    "result": dmarc_report["record"]
  }

  # Tags to use on the dmarc test
  tags_map = [
    ("policy", "p"),
    ("subdomain_policy", "sp"),
    ("rua", "rua"),
    ("dkim_alignment", "adkim"),
    ("spf_alignment", "aspf"),
  ]

  tags = dmarc_report["parsed"]["tags"]

  # CHECKDMARC TEST
  verify_result["tests"]["checkdmarc"] = {
    "result": [
      {
        "element": header,
        "value": tags.get(tag, {}).get("value", "not_found"),
        "explicit": tags.get(tag, {}).get("explicit", None)
      }
      for header, tag in tags_map
    ]
  }

  if 'X-Spamd-Result' in email_str:
    header_value = email_str['X-Spamd-Result']

    match = re.search(r'(DMARC_[A-Z_]+)', header_value)
    if match:
      dmarc_result = match.group(1)

      if dmarc_result == "DMARC_POLICY_ALLOW":
        verify_result['tests']["rspamd"] = {
          "result": "Message passed DMARC verification",
          "dmarc": dmarc_result
        }
      elif dmarc_result in ("DMARC_POLICY_REJECT", "DMARC_POLICY_QUARANTINE"):
        verify_result['status'] = "error"
        verify_result["subtract"] = score.subtract("dmarc", Score.DMARC_ERR.value)
        verify_result['tests']["rspamd"] = {
          "result": f"Authentication failed. Rejection/Quarantine suggested",
          "dmarc": dmarc_result
        }
      elif dmarc_result == "DMARC_POLICY_SOFTFAIL":
        verify_result['status'] = "error"
        verify_result["subtract"] = score.subtract("dmarc", Score.DMARC_ERR.value)
        verify_result['tests']["rspamd"] = {
          "result": f"Authentication failed. No action suggested by policy",
          "dmarc": dmarc_result
        }
      elif dmarc_result == "DMARC_NA":
        verify_result['status'] = "warning"
        verify_result['tests']["rspamd"] = {
          "result": "No DMARC policy or From header found",
          "dmarc": dmarc_result
        }
      elif dmarc_result == "DMARC_BAD_POLICY":
        verify_result['status'] = "error"
        verify_result["subtract"] = score.subtract("dmarc", Score.DMARC_ERR.value)
        verify_result['tests']["rspamd"] = {
          "result": "Invalid or multiple DMARC policies",
          "dmarc": dmarc_result
        }
    else:
      verify_result['tests']["rspamd"] = {
        "result": "No DMARC result detected"
      }

  return verify_result

async def verify_domain_mx(domain, score):
  verify_result = {
    "status": "warning",
    "tests": {}
  }

  mx_dns_result = await DNS.resolve(domain, "MX", "mx")

  if mx_dns_result["status"] != "success":
    # DNS TEST IN CASE OF ERROR
    verify_result["tests"]["dns"] = {
      "result": mx_dns_result["message"]
    }
    verify_result["status"] = "error"
    verify_result["subtract"] = score.subtract("mx", Score.MX_WARN.value)
    return verify_result

  verify_result["status"] = "success"

  # DNS TEST
  verify_result["tests"]["dns"] = {
    "result": [
      [rdata.preference, rdata.exchange.to_unicode()]
      for rdata in mx_dns_result["data"]
    ]
  }

  return verify_result

async def verify_dkim(domain, email, email_str, score):
  verify_result = {
    "status": "success",
    "tests": {}
  }

  if "DKIM-Signature" not in email_str:
    verify_result["status"] = "warning"
    # DKIMPY TEST IN CASE OF ERROR
    verify_result["tests"]["dkimpy"] = {
      "result": "No DKIM-Signature header present"
    }
    verify_result["subtract"] = score.subtract("dkim", Score.DKIM_NO.value)
    return verify_result

  try:
    if dkim.verify(email) is True:
      # DKIMPY TEST
      verify_result["tests"]["dkimpy"] = {
        "result": "Message passed DKIM validation"
      }
    else:
      raise dkim.DKIMException("Message did not pass DKIM validation")
  except dkim.DKIMException:
    verify_result["status"] = "error"
    verify_result["tests"]["dkimpy"] = {
      "result": "Message did not pass DKIM validation"
    }
    verify_result["subtract"] = score.subtract("dkim", Score.DKIM_ERR.value)

  pattern_dkim = r"v=((?P<version>[^;]+))|a=((?P<algorithm>[^;]+))|c=((?P<canonicalization>[^;]+))|d=((?P<domain>[^;]+))|s=((?P<selector>[^;]+))|t=((?P<timestamp>[^;]+))|bh=((?P<body_hash>[^;]+))|h=((?P<signed_headers>[^;]+))|b=((?P<signature>[^;]+))"
  header_result = {}
  dkim_selector = ""

  match_dkim = re.finditer(pattern_dkim, re.sub(r"\s+", "", email_str["DKIM-Signature"]))
  for result in match_dkim:
    for name, value in result.groupdict().items():
      if value is not None:
        header_result[name] = value
        if name == "selector":
          dkim_selector = value

  if header_result:
    verify_result["tests"]["header"] = {
      "result": header_result
    }

  if dkim_selector:
    dkim_dns_result = await DNS.resolve(f"{dkim_selector}._domainkey.{domain}", "TXT", "dkim")

    if dkim_dns_result["status"] != "success":
      # DNS TEST
      verify_result["tests"]["dns"] = {
        "result": dkim_dns_result["message"]
      }
      return verify_result

    verify_result["tests"]["dns"] = {
      "result": [rdata.strings[0].decode("utf-8") for rdata in dkim_dns_result["data"]]
    }

  return verify_result

async def verify_arc(email):
  verify_result = {
    "status": "success",
    "tests": {}
  }

  try:
    cv, res, reason = dkim.arc_verify(email)

    if isinstance(cv, bytes):
      cv = cv.decode("utf-8")
    if isinstance(reason, bytes):
      reason = reason.decode("utf-8")

    if cv == "pass":
      verify_result["tests"]["dkimpy"] = {
        "result": reason or "ARC validation passed"
      }
    elif cv == "fail":
      verify_result["status"] = "error"
      verify_result["tests"]["dkimpy"] = {
        "result": reason or "ARC validation failed"
      }
    elif cv == "none":
      verify_result["status"] = "info"
      verify_result["tests"]["dkimpy"] = {
        "result": "No ARC signature found"
      }
    else:
      verify_result["status"] = "warning"
      verify_result["tests"]["dkimpy"] = {
        "result": f"Unexpected cv value: {cv}"
      }

  except dkim.DKIMException as e:
    verify_result["status"] = "error"
    verify_result["tests"]["dkimpy"] = {
      "result": f"Error validating ARC chain: {e}"
    }
  except Exception as e:
    verify_result["status"] = "error"
    verify_result["tests"]["dkimpy"] = {
      "result": f"Unexpected error: {e}"
    }

  return verify_result
