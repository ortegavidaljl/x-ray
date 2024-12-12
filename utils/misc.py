import dns.resolver
import dns.asyncresolver

class DNS:
  
  async def resolve(name_ip, record_type, check_type):
    custom_dns_messages = {
      "spf": {
        "NXDOMAIN": "Domain doesn't have an SPF record",
      },
      "dmarc": {
        "NoAnswer": f"DMARC record {name_ip} was not found on domain's zone",
        "NXDOMAIN": "Domain doesn't have a DMARC record",
      },
      "dkim": {
        "NoAnswer": f"DKIM record {name_ip} was not found on domain's zone",
        "NXDOMAIN": "Domain doesn't have a DKIM record",
      },
      "mx": {
        "NoAnswer": "Domain doesn't have MX records",
        "NXDOMAIN": "Domain doesn't have MX records",
      }
    }

    try:
      # Realiza la consulta DNS de forma asíncrona
      result = await dns.asyncresolver.resolve(name_ip, record_type)
      # Devuelve los resultados de manera estructurada
      return {"status": "success", "data": result}
    except dns.resolver.LifetimeTimeout:
      return {"status": "LifetimeTimeout", "message": custom_dns_messages.get(check_type, {}).get("LifetimeTimeout", "The resolution litefime expired") }
    except dns.asyncresolver.NoAnswer:
      return {"status": "NoAnswer", "message": custom_dns_messages.get(check_type, {}).get("NoAnswer", "The DNS response does not contain an answer") }
    except dns.resolver.NoNameservers:
      return {"status": "NoNameservers", "message": custom_dns_messages.get(check_type, {}).get("NoNameservers", "All nameservers failed to answer the query") }
    except dns.asyncresolver.NXDOMAIN:
      return {"status": "NXDOMAIN", "message": custom_dns_messages.get(check_type, {}).get("NXDOMAIN", "DNS RR does not exists") }
    except Exception as e:
      return {"status": "Other", "message": str(e)}