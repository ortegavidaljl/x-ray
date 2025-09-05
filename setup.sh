#!/bin/bash
set -e

# ENV INJECTION --------

load_env() {
  if [ -f .env ]; then
  set -a
    source .env
    set +a
  fi

  validate_env
}

# ENV VALIDATION --------

validate_env() {
  if [ "$WEBAPP" != "true" ]; then
    REQUIRED_VARS=(DB_HOST DB_PORT DB_USERNAME DB_PASSWORD DB_DATABASE)

    for var in "${REQUIRED_VARS[@]}"; do
      if [[ -z "${!var}" ]]; then
        echo "[!] Undefined environment variable: $var"
        exit 1
      fi
    done
  fi
}

# DEPENDENCY INSTALLATION --------

install_packages() {
  if command -v apt-get >/dev/null; then
    echo "=> Installing packages with apt-get ..."
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      lsb-release curl gpg wget gettext gnupg \
      postfix postfix-mysql mariadb-client \
      clamav clamav-daemon clamav-freshclam \
      spf-tools-perl python3 python3-pip python3.11-venv

    CODENAME=`lsb_release -c -s`
    mkdir -p /etc/apt/keyrings
    wget -O- https://rspamd.com/apt-stable/gpg.key | gpg --dearmor | tee /etc/apt/keyrings/rspamd.gpg > /dev/null
    echo "deb [signed-by=/etc/apt/keyrings/rspamd.gpg] http://rspamd.com/apt-stable/ $CODENAME main" | tee /etc/apt/sources.list.d/rspamd.list
    echo "deb-src [signed-by=/etc/apt/keyrings/rspamd.gpg] http://rspamd.com/apt-stable/ $CODENAME main"  | tee -a /etc/apt/sources.list.d/rspamd.list
    apt-get update
    apt-get install -y --no-install-recommends rspamd

    apt-get clean
  fi
}

# PYTHON ENV SETUP --------

setup_python_env() {
  echo "=> Creating virtual environment..."
  python3 -m venv $APP_DIR/venv
  source $APP_DIR/venv/bin/activate

  if [ -f "$APP_DIR"/requirements.txt ]; then
    echo "=> Installing dependencies from requirements.txt ..."
    pip install --no-cache-dir -r $APP_DIR/requirements.txt
  else
    echo "[!] Failed to find requirements.txt, skipping Python package installation"
  fi
}

# SYSTEM USER/GROUP CREATION --------

create_users() {
  echo "=> Checking system users/groups ..."

  if ! getent group vpostfix >/dev/null; then
    groupadd -g 1120 vpostfix
  fi

  if ! getent passwd vpostfix >/dev/null; then
    useradd -u 1120 -g vpostfix -s /bin/false -d /nonexistent vpostfix
  fi

  if ! getent group rspamd >/dev/null; then
    groupadd -g 1111 rspamd
  fi

  if ! getent passwd rspamd >/dev/null; then
    useradd -u 1111 -g rspamd -s /usr/sbin/nologin -d /home/rspamd -r rspamd
  fi

  if ! getent group clamav >/dev/null; then
    groupadd -g 1113 clamav
  fi

  if ! getent passwd clamav >/dev/null; then
    useradd -u 1113 -g clamav -s /usr/sbin/nologin -d /nonexistent -r clamav
  fi
}

# DB DEPLOYMENT --------

deploy_db() {
  if [ "$WEBAPP" = "true" ]; then
    echo "[!] DB won't be deployed because the WEBAPP variable was set to true"
  else
    echo "=> Starting database setup ..."
    export MYSQL_PWD="$DB_PASSWORD"
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USERNAME" "$DB_DATABASE" < $APP_DIR/database.sql
    if [ -n "$DOMAIN" ]; then
      mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USERNAME" "$DB_DATABASE" -e "INSERT IGNORE INTO domains (name, active) VALUES ('$DOMAIN', 1)"
    else
      echo "[!] DOMAIN variable empty or not defined. A domain must be created via CLI or DB"
    fi

    unset MYSQL_PWD
  fi
}

# SERVICE CONFIGURATION --------

configure_services() {
  echo "=> Creating/updating configuration ..."

  mkdir -p /var/mail/virtual_domains /var/run/clamav
  chown -R vpostfix:vpostfix /var/mail/virtual_domains
  chown -R clamav:clamav /var/run/clamav
  chmod 755 /var/run/clamav

  cat $APP_DIR/templates/master.cf >> /etc/postfix/master.cf
  cp $APP_DIR/templates/main.cf /etc/postfix/main.cf
  envsubst < $APP_DIR/templates/virtual_domains.cf > /etc/postfix/virtual_domains.cf
  envsubst < $APP_DIR/templates/virtual_users.cf > /etc/postfix/virtual_users.cf
  cp -r $APP_DIR/templates/rspamd/local.d/* /etc/rspamd/local.d/
  cp -r $APP_DIR/templates/rspamd/override.d/* /etc/rspamd/override.d/

  if [ "$DISABLE_FRESHCLAM_TEST" = "true" ]; then
    echo "[!] Freshclam database test has been disabled"
    sed -i -e 's/TestDatabases yes/TestDatabases no/g' /etc/clamav/freshclam.conf
  fi

  sed -i 's/^LogFile/#&/' /etc/clamav/clamd.conf
  sed -i 's/^LogSyslog/#&/' /etc/clamav/clamd.conf

  freshclam --quiet

  if is_container; then
  cat <<EOF > /etc/crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

4 * * * * root /usr/bin/freshclam --quiet
EOF
  fi
}

# SYSTEMD --------

configure_systemd() {
  if command -v systemctl >/dev/null && systemctl --version >/dev/null 2>&1; then
    echo "=> Configuring systemd ..."
    envsubst < $APP_DIR/templates/xray.service > /etc/systemd/system/xray.service
    systemctl daemon-reload
    systemctl enable rspamd
    systemctl enable xray
    systemctl enable postfix
    systemctl enable clamav-daemon
    systemctl start clamav-daemon
    systemctl start rspamd
    systemctl start xray
    systemctl start postfix
  else
    if is_container; then
      echo -e "[!] Container environment detected. Services will be managed by s6 ..."
    else
      echo "[!] Services shall be started manually"
    fi
  fi
}

# FINISH --------

finish() {
  touch $APP_DIR/.setup_done
  echo "[+] Setup successfully completed"
}

is_container() {
  if [ -f /.dockerenv ]; then
    return 0
  elif grep -qE 'docker|kubepods|containerd' /proc/1/cgroup 2>/dev/null; then
    return 0
  else
    return 1
  fi
}

main() {
  if [ $UID -ne 0 ];then
    echo "This script must be run by root"
    exit 1
  fi

  if is_container; then
    APP_DIR="/opt/x-ray"
    MODE="container"
  else
    APP_DIR="$(pwd)"
    MODE="normal"
  fi

  if [ -f "$APP_DIR"/.setup_done ]; then
    echo "[!] Setup has already been executed"
    exit 0
  fi

  case "$MODE" in
    container)
      load_env
      deploy_db
      configure_services
      finish
      ;;
    normal)
      load_env
      install_packages
      setup_python_env
      create_users
      deploy_db
      configure_services
      configure_systemd
      finish
      ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main
fi