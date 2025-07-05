#!/bin/bash
set -e

if [ -f .setup_done ]; then
  echo "✅ Setup has already been executed. Skipping..."
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
    echo "❌ Undefined environment variable: $var"
    exit 1
  fi
done

echo "✅ Variables loaded successfully"

# --------- INSTALACIÓN DE DEPENDENCIAS ---------
if command -v apt-get >/dev/null; then
  echo "📦 Installing packages with apt-get..."
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
echo "🐍 Creating virtual environment in /app/venv..."
python3 -m venv /app/venv
source /app/venv/bin/activate

if [ -f requirements.txt ]; then
  echo "📦 Installing dependencies from requirements.txt..."
  pip install --no-cache-dir -r requirements.txt
else
  echo "⚠️ Failed to find requirements.txt, skipping Python package installation."
fi

# --------- CREACIÓN DE USUARIOS Y GRUPOS ---------
echo "👤 Checking system users/groups..."

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
echo "🛠️ Starting database setup..."
export MYSQL_PWD="$DB_PASSWORD"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USERNAME" "$DB_DATABASE" < ./database.sql
if [ -n "$DOMAIN" ]; then
  mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USERNAME" "$DB_DATABASE" -e "INSERT INTO domains (name, active) VALUES ('$DOMAIN', 1)"
else
  echo "⚠️ DOMAIN variable empty or not defined. A domain must be created via CLI or DB."
fi

unset MYSQL_PWD

# --------- CONFIGURACIÓN ---------
echo "⚙️ Applying Postfix/Spamassassin configuration..."

envsubst < templates/main.cf > /etc/postfix/main.cf
sed -i '/^smtp\s\+inet\s\+.*smtpd\s*$/a \
  -o content_filter=spamassassin:dummy -o receive_override_options=no_address_mappings -o smtp_send_xforward_command=yes
' /etc/postfix/master.cf
cat templates/master.cf >> /etc/postfix/master.cf
envsubst < templates/virtual_domains.cf > /etc/postfix/virtual_domains.cf
envsubst < templates/virtual_users.cf > /etc/postfix/virtual_users.cf
cp templates/local.cf /etc/mail/spamassassin/local.cf

echo "📥 Updating SpamAssassin rules..."
runuser -u spamd -- sa-update || echo "⚠️ Could not download spam rules (may be offline or already updated)."

# --------- SYSTEMD (opcional) ---------
if command -v systemctl >/dev/null && systemctl --version >/dev/null 2>&1; then
  echo "🔌 Installing X-Ray service with systemd..."
  export DIRECTORY=$(pwd)
  envsubst < templates/xray.service > /etc/systemd/system/xray.service
  systemctl daemon-reload
  systemctl enable spamd
  systemctl enable xray
  systemctl enable postfix
  systemctl start spamd
  systemctl start xray
  systemctl start postfix
  
else
  if [ -f /.dockerenv ]; then
    echo -e "🐳 Docker environment detected. Services will be started by entrypoint.sh..."
    echo -e "⚙️ Setting rsyslog..."
    sed -i 's/^module(load="imklog")/#module(load="imklog")/' /etc/rsyslog.conf
  else
    echo "⚠️ Services shall be started manually."
  fi
fi

echo "✅ Setup successfully completed."
touch .setup_done