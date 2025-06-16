#!/bin/bash
set -e

GREEN='\033[0;32m'
NC='\033[0m' # Sin color

# Ejecuta el setup si no está hecho
if [ ! -f .setup_done ]; then
  /app/setup.sh
fi

# Luego lanza supervisord
#exec supervisord -c /app/templates/supervisord.conf

# Lanza rsyslog
echo -e "📡 Arrancando rsyslog..."
rsyslogd && echo -e "${GREEN}✅ rsyslog lanzado${NC}"

# Lanza spamd (sin init.d mejor, directamente)
echo -e "🛡️ Arrancando spamd..."
/usr/sbin/spamd -d -c -m 5 && echo -e "${GREEN}✅ spamd lanzado${NC}"

# Lanza postfix en foreground
echo -e "📮 Arrancando Postfix..."
/usr/sbin/postfix start-fg &
echo -e "${GREEN}✅ Postfix lanzado${NC}"

# Lanza tu script Python
echo -e "🧠 Arrancando X-Ray..."
source /app/venv/bin/activate
/app/venv/bin/python /app/x-ray.py &
echo -e "${GREEN}✅ X-Ray lanzado${NC}"

echo -e "🟢 Arranque completo."
tail -f /dev/null