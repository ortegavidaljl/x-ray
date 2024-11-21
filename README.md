# X-Ray

This is the repo for X-Ray, a project written in Python that analyses an incoming email and generates a complete report, including information about sender authentication, server configuration and RBL listing, among other useful things.

The script is made to work as an advanced Postfix content filter, though it could be modified to work without it. The report has been designed to feed a webapp, so it is possible to make a self-hosted mailing checking platform.

All reports are saved in a MySQL database. Below there's an image showing its structure and a dump:

Database can be imported directly using the file .sql provided in this repo.

All contributions are welcomed.

## Requirements

Apart from Python 3.11.9 (minimum), X-Ray needs the following packages to work:

- [aiosmtpd](https://pypi.org/project/aiosmtpd/) >= 1.4.6
- [pymysql](https://pypi.org/project/pymysql/) >= 1.1.1
- [dkimpy](https://pypi.org/project/dkimpy/) >= 1.1.7
- [dnspython](https://pypi.org/project/dnspython/) >= 2.6.1
- [uuid_utils](https://pypi.org/project/uuid-utils/) >= 0.8.0
- [python-dotenv](https://pypi.org/project/python-dotenv/) >= 1.0.1

Components available in standard library are not listed. To avoid errors, the script will check if everything is present in every start.

## Installation script

This repo also contains a Bash script called install.sh to simplify the installation process of the script and its environment (Postfix included). The script is is made for AlmaLinux 8.x and newer (it can be modified to run on other systems), and perform the following tasks:

- Installs Python 3.11, Postfix and its connector for MySQL, spamassassin with pyzor, and a MySQL client (from mariadb package)
- Installs pip and the needed dependencies.
- Creates a virtual user for Postfix and applies some configuration changes to Postfix to allow MySQL virtual domains/users.
- Imports the database.sql file and creates a new domain.
- Creates a content filter, integrating X-Ray.
- Configures Spamassassin and integrates it also with Postfix.
- Creates a systemd service for X-Ray, and enables/start services so everything can work together.

Before running the installer or the X-Ray script, it is necessary to specify some data in the .env file.

## Configuration

As mentioned before, the script needs some data to work. These are the items that can be configured in the .env file:

<table>
  <tr><th>Value</th><th>Info</th></tr>

  <tr><td colspan="2" align="center">:warning: Mandatory</td></tr>
  <tr><td>* HOSTNAME</td><td>The hostname the aiosmtpd service will use. If not specified, <strong>127.0.0.1</strong> will be used.</td></tr>
  <tr><td>* PORT</td><td>The port the script will be listening. If not specified, <strong>10031</strong> will be used.</td></tr>
  <tr><td>* DB_HOST</td><td>The hostname used for MySQL connection. If not specified, <strong>127.0.0.1</strong> will be used.</td></tr>
  <tr><td>* DB_PORT</td><td>The port used for MySQL connection. If not specified, <strong>3306</strong> will be used.</td></tr>
  <tr><td>DB_DATABASE</td><td>The name of the database that contains the needed structure (see database.sql file). This field is <strong>needed</strong>, so the script will not work if it isn't present.</td></tr>
  <tr><td>DB_USERNAME</td><td> The user for the database connection. This field is also <strong>needed</strong>.</td></tr>
  <tr><td>DB_PASSWORD</td><td>The user's password. This field is also <strong>needed</strong>.</td></tr>

  <tr><td colspan="2" align="center">:warning: Optional</td></tr>
  <tr><td>SCORE_SPAMASSASSIN_SPAM</td><td>Points subtracted in case spamassassin detects the email as spam. By default, 3.</td></tr>
  <tr><td>SCORE_SPF_ERR</td><td>Points subtracted in case SPF is not correct or duplicated. By default, 3.</td></tr>
  <tr><td>SCORE_SPF_WARN</td><td>Points subtracted in case SPF softfails or any other error occurs. By default, 1.5.</td></tr>
  <tr><td>SCORE_MX_WARN</td><td>Points subtracted if domain doesn't have MX records or they cannor resolve. By default, 1.</td></tr>
  <tr><td>SCORE_RDNS_WARN</td><td>Points subtracted if server's helo doesn't equals rdns. By default, 1.</td></tr>
  <tr><td>SCORE_DKIM_NO</td><td>Points subtracted if domain doesn't have DKIM. By default, 1.</td></tr>
  <tr><td>SCORE_DKIM_ERR</td><td>Points subtracted in case domain's DKIM don't pass validation. By default, 3.</td></tr>
  <tr><td>SCORE_RBL_ERR</td><td>Points subtracted if server sending IP is listed in one or more RBL. By default, 1.5.</td></tr>
</table>

\* Only mandatory if using the installer script.