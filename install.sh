#!/bin/bash

# Update server and install dependencies
dnf update -y
dnf install python3.11 postfix postfix-mysql spamassassin pyzor mariadb -y

# Install pip and python dependencies
wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py && python3.11 /tmp/get-pip.py
python3.11 -m pip install aiosmtpd dkimpy dnspython mysql-connector-python uuid-utils python-dotenv

# Create virtual user and group for postfix
groupadd vpostfix && useradd vpostfix -g vpostfix -s /sbin/nologin -c "Virtual postfix user" -d /var/empty
user_id=$(getent passwd "vpostfix" | cut -d: -f3)
group_id=$(getent group "vpostfix" | cut -d: -f3)

# Backup postfix main.cf file
postfix_main="/etc/postfix/main.cf"
cp $postfix_main $postfix_main.ORIG

# Edit postfix interfaces in main.cf
sed -i 's/^inet_interfaces = localhost/#inet_interfaces = localhost/' $postfix_main
sed -i 's/^#inet_interfaces = all/inet_interfaces = all/' $postfix_main
sed -i 's/^#home_mailbox = Maildir/home_mailbox = Maildir/' $postfix_main

# Configure virtual domains and users
cat <<EOL >> $postfix_main
# Virtual domains, users, and aliases
virtual_mailbox_domains = mysql:/etc/postfix/virtual_domains.cf
virtual_mailbox_maps = mysql:/etc/postfix/virtual_users.cf
virtual_mailbox_base = /var/mail/virtual_domains
virtual_minimum_uid = $user_id
virtual_uid_maps = static:$user_id
virtual_gid_maps = static:$group_id
EOL

# Create email dir
mkdir /var/mail/virtual_domains
chown -R vpostfix:vpostfix /var/mail/virtual_domains

. ./env

# Create database and user for virtual configy

export MYSQL_PWD="$DB_PASSWORD"

mysql -h $DB_HOST -P $DB_PORT -u $DB_USERNAME $DB_DATABASE < ./database.sql

export MYSQL_PWD=""

cat << EOF > /etc/postfix/virtual_domains.cf
user = $DB_USERNAME
password = $DB_PASSWORD
hosts = $DB_HOST
dbname = $DB_DATABASE
query = SELECT 1 from domains WHERE name='%s'
EOF

cat << EOF > /etc/postfix/virtual_users.cf
user = $DB_USERNAME
password = $DB_PASSWORD
hosts = $DB_HOST
dbname = $DB_DATABASE
query = SELECT 1 from accounts WHERE name='%s'
EOF

read -p "Enter a domain name (to be used for email accounts): " new_domain

export MYSQL_PWD="$DB_PASSWORD"

mysql -h $DB_HOST -P $DB_PORT -u $DB_USERNAME -e "INSERT INTO domains (name) VALUES ($new_domain)"

export MYSQL_PWD=""

cat << EOF >> /etc/postfix/main.cf
content_filter=scan:[127.0.0.1]:$PORT
receive_override_options = no_address_mappings
smtp_send_xforward_command=yes
EOF

sed -i '/^smtp\s\+inet\s\+n\s\+-\s\+n\s\+-\s\+-\s\+smtpd/s/.*/smtp      inet  n       -       n       -       -       smtpd -o content_filter=spamassassin:dummy -o receive_override_options=no_address_mappings -o smtp_send_xforward_command=yes/' master.cf

cat << 'EOF' >> /etc/postfix/master.cf
spamassassin unix -     n       n       -       -       pipe
  user=spamd argv=/usr/bin/spamc -f -e
  /usr/sbin/sendmail.postfix -oi -f ${sender} ${recipient}

scan      unix  -       -       n       -       10      smtp
      -o smtp_send_xforward_command=yes
      -o disable_mime_output_conversion=yes

localhost:10032 inet  n       -       n       -       10      smtpd
      -o smtpd_authorized_xforward_hosts=127.0.0.0/8
      -o content_filter=
      -o receive_override_options=no_unknown_recipient_checks
      -o smtp_send_xforward_command=yes
EOF

cat << 'EOF' >> /etc/mail/spamassassin/local.cf
use_pyzor 1
pyzor_timeout 10

add_header all Status _YESNOCAPS_
add_header all Score _SCORE_
add_header all Required _REQD_
add_header all Report _REPORT_
add_header all Pyzor _PYZOR_
EOF

mkdir /home/spamassassin
groupadd spamd
useradd -g spamd -s /bin/false -d /home/spamassassin spamd
chown -R spamd:spamd /home/spamassassin

systemctl enable spamassassin && systemctl start spamassassin
systemctl enable postfix && systemctl start postfix

cat << 'EOF' >> /etc/systemd/system/xray.service
[Unit]
Description=X-Ray mail processor

[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/python3.11 $(pwd)/x-ray.py

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload && systemctl enable xray && systemctl start xray