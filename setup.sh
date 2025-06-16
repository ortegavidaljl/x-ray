#!/bin/bash
set -e

if [ -f .setup_done ]; then
  echo "✅ Setup ya fue ejecutado. Saltando..."
  exit 0
fi

# --------- ENV INJECTION ---------
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# --------- VALIDACIÓN ---------
REQUIRED_VARS=(
  DB_HOST DB_PORT DB_USERNAME DB_PASSWORD DB_DATABASE
  DOMAIN PORT
)

for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var}" ]]; then
    echo "❌ Variable de entorno no definida: $var"
    exit 1
  fi
done

echo "✅ Variables cargadas correctamente"

# --------- INSTALACIÓN DE DEPENDENCIAS ---------
if command -v apt-get >/dev/null; then
  echo "📦 Instalando paquetes con apt-get..."
  apt-get update
  apt-get install -y --no-install-recommends \
    postfix postfix-mysql \
    spamassassin spamc spamd pyzor spfquery \
    mariadb-client rsyslog \
    python3 python3-pip python3.11-venv \
    gettext gnupg
  apt-get clean
fi

# --------- ENTORNO PYTHON ---------
echo "🐍 Creando entorno virtual en /app/venv..."
python3 -m venv /app/venv
source /app/venv/bin/activate

if [ -f requirements.txt ]; then
  echo "📦 Instalando dependencias desde requirements.txt..."
  pip install --no-cache-dir -r requirements.txt
else
  echo "⚠️ No se encontró requirements.txt, omitiendo instalación de paquetes Python."
fi

# --------- CREACIÓN DE USUARIOS Y GRUPOS ---------
echo "👤 Verificando usuarios/grupos del sistema..."

if ! getent group vpostfix >/dev/null; then
  groupadd -g 1111 vpostfix
fi

if ! getent passwd vpostfix >/dev/null; then
  useradd -u 1111 -g vpostfix -s /bin/false -d /nonexistent vpostfix
fi

if ! getent group spamd >/dev/null; then
  groupadd -g 1112 spamd
fi

if ! getent passwd spamd >/dev/null; then
  useradd -u 1112 -g spamd -s /bin/false -d /home/spamassassin spamd
fi

mkdir -p /var/mail/virtual_domains /home/spamassassin
chown -R vpostfix:vpostfix /var/mail/virtual_domains
chown -R spamd:spamd /home/spamassassin

# --------- BASE DE DATOS ---------
echo "🛠️ Iniciando setup de base de datos..."
export MYSQL_PWD="$DB_PASSWORD"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USERNAME" "$DB_DATABASE" < ./database.sql
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USERNAME" "$DB_DATABASE" -e "INSERT INTO domains (name) VALUES ('$DOMAIN')"
unset MYSQL_PWD

# --------- CONFIGURACIÓN ---------
echo "⚙️ Aplicando configuración..."

envsubst < templates/main.cf > /etc/postfix/main.cf
sed -i '/^smtp\s\+inet\s\+.*smtpd\s*$/a \
  -o content_filter=spamassassin:dummy -o receive_override_options=no_address_mappings -o smtp_send_xforward_command=yes
' /etc/postfix/master.cf
cat templates/master.cf >> /etc/postfix/master.cf
envsubst < templates/virtual_domains.cf > /etc/postfix/virtual_domains.cf
envsubst < templates/virtual_users.cf > /etc/postfix/virtual_users.cf
cp templates/local.cf /etc/mail/spamassassin/local.cf

echo "📥 Actualizando reglas de SpamAssassin..."
runuser -u spamd -- sa-update || echo "⚠️ No se pudieron descargar las reglas de spam (puede que no haya conexión o ya estén actualizadas)."

# --------- SYSTEMD (opcional) ---------
if command -v systemctl >/dev/null && systemctl --version >/dev/null 2>&1; then
  echo "🔌 Instalando servicio X-Ray con systemd..."
  export DIRECTORY=$(pwd)
  envsubst < templates/xray.service > /etc/systemd/system/xray.service
  systemctl daemon-reexec
  systemctl enable spamassassin postfix xray
  systemctl start spamassassin postfix xray
else
  if [ -f /.dockerenv ]; then
    echo -e "🐳 Detectado entorno Docker. Los servicios serán arrancados por entrypoint.sh. Ajustando rsyslog..."
    sed -i 's/^module(load="imklog")/#module(load="imklog")/' /etc/rsyslog.conf
  else
    echo "⚠️ Los servicios deberán iniciarse manualmente."
  fi
fi

echo "✅ Setup completado con éxito."
touch .setup_done