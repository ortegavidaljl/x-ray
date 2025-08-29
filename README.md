# X-Ray

This is the repo for X-Ray, a project written in Python that analyses an incoming email and generates a complete report, including information about sender authentication, server configuration and RBL listing, among other useful things.

The script is made to work as an advanced Postfix content filter, though it could be modified to work without it. The report has been designed to feed a webapp, so it is possible to make a self-hosted mailing checking platform.

All contributions are welcomed.

## Requirements

Apart from Python 3.11.9 (minimum), X-Ray needs the following packages to work:

- Python (can be installed using requirements.txt):
  - [aiosmtpd](https://pypi.org/project/aiosmtpd/)
  - [pymysql](https://pypi.org/project/pymysql/)
  - [dkimpy](https://pypi.org/project/dkimpy/)
  - [dnspython](https://pypi.org/project/dnspython/)
  - [uuid_utils](https://pypi.org/project/uuid-utils/)
  - [python-dotenv](https://pypi.org/project/python-dotenv/)
  - [cryptography](https://pypi.org/project/cryptography/)
  - [checkdmarc](https://pypi.org/project/checkdmarc/)
- Others:
  - spfquery (it may be available by default in your distro's repositories, or it can be installed from the PERL module installer. The package is called Mail::SPF)
  - MariaDB server
  - Postfix and its postfix-mysql package
  - Rspamd
  - ClamAV

Components available in standard library are not listed. To avoid errors, the script will check if everything is present in every start.

## Example of integration

Here are some gifs of a webapp I made in vue and PHP (Laravel) to be able to create random email accounts and view reports. The application is called Mail Insights, and is growing bit by bit in [its repo](https://github.com/ortegavidaljl/mail-insights).

<div align="center">
  <img width="49.5%" src="/assets/mail_insights_xray1.gif"/>
  <img width="49.5%" src="/assets/mail_insights_xray2.gif"/>
</div>

### Database

The script stores generated reports in a database. The same db is also used for virtual domain/user checks in Postfix. Since there's a lot of information in each report, the generated json is saved directly into the database. A sql file with the needed structure is provided in this repo, so it can be imported into your database.

<div align="center">
  <img src="/assets/database_tables.png" alt="Screenshot of the database schema"/>
</div>

## Installation script

This repo also contains a Bash script called install.sh to simplify the installation process of the script and its environment (Postfix included). The script is is made for Debian 12 and newer (it can be modified to run on other systems), and perform the following tasks:

- Installs Python, Postfix and its connector for MySQL, Rspamd, and a MySQL client (from mariadb package)
- Installs pip and the needed dependencies.
- Creates a virtual user for Postfix and applies some configuration changes to Postfix to allow MySQL virtual domains/users.
- Imports the database.sql file and creates a new domain.
- Creates a content filter, integrating X-Ray.
- Configures Rspamd and integrates it with Postfix.
- Creates a systemd service for X-Ray, and enables/start services so everything can work together.

> [!WARNING]
> * Before running the installer or the X-Ray script, it is necessary to specify some data in the .env file.
> * If you don't want to use the installation script, make sure to create a domain in the "domains" table. Of course, one or more email names are needed in order for emails to be received. You can use another script or webapp to generate them as needed.

## Configuration

As mentioned before, the script needs some data to work. These are the items that can be configured in the .env file:

<table>
  <tr><th>Value</th><th>Info</th></tr>

  <tr><td colspan="2" align="center">:warning: Mandatory</td></tr>
  <tr><td>* PORT</td><td>The port the script will be listening. If not specified, <strong>10031</strong> will be used.</td></tr>
  <tr><td>* DB_HOST</td><td>The host used for MySQL connection. If not specified, <strong>127.0.0.1</strong> will be used.</td></tr>
  <tr><td>* DB_PORT</td><td>The port used for MySQL connection. If not specified, <strong>3306</strong> will be used.</td></tr>
  <tr><td>DB_DATABASE</td><td>The name of the database that contains the needed structure (see database.sql file). This field is <strong>needed</strong>, so the script will not work if it isn't present.</td></tr>
  <tr><td>DB_USERNAME</td><td> The user for the database connection. This field is also <strong>needed</strong>.</td></tr>
  <tr><td>DB_PASSWORD</td><td>The user's password. This field is also <strong>needed</strong>.</td></tr>

  <tr><td colspan="2" align="center">:warning: Optional</td></tr>
  <tr><td>HOST</td><td>The host the aiosmtpd service will use. If not specified, <strong>127.0.0.1</strong> will be used.</td></tr>
  <tr><td>WEBAPP</td><td>If set to true, the script won't deploy the x-ray database. This is preferred in case Mail Insights is going to be used.</td></tr>
  <tr><td>DISABLE_FRESHCLAM_TEST</td><td>If the machine you're deploying this service has less than 3 GB of available RAM, maybe you should want to set this to true. If done, freshclam won't test the downloaded databases, so less RAM will be used in this process. Use this with caution.</td></tr>
  <tr><td>DOMAIN</td><td>If set, and WEBAPP is false or not set, the installation script will create the domain directly after deploying the database.</td></tr>
  <tr><td>ENCRYPTION</td><td>If enabled, clients must generate a key pair and upload their public key when creating an account. This allows emails sent to them later to be encrypted. If disabled, reports will be saved in plain text, and no asymmetric keys will be required. By default, false.</td></tr>
  <tr><td>SCORE_RSPAMD_SPAM</td><td>Points subtracted in case Rspamd detects the email as spam. By default, 3.</td></tr>
  <tr><td>SCORE_DMARC_ERR</td><td>Points subtracted in case DMARC check is not ok. By default, 4.</td></tr>
  <tr><td>SCORE_SPF_ERR</td><td>Points subtracted in case SPF is not correct or duplicated. By default, 3.</td></tr>
  <tr><td>SCORE_SPF_WARN</td><td>Points subtracted in case SPF softfails or any other error occurs. By default, 1.5.</td></tr>
  <tr><td>SCORE_MX_WARN</td><td>Points subtracted if domain doesn't have MX records or they cannor resolve. By default, 1.</td></tr>
  <tr><td>SCORE_RDNS_WARN</td><td>Points subtracted if server's helo doesn't equals rdns. By default, 1.</td></tr>
  <tr><td>SCORE_DKIM_NO</td><td>Points subtracted if domain doesn't have DKIM. By default, 1.</td></tr>
  <tr><td>SCORE_DKIM_ERR</td><td>Points subtracted in case domain's DKIM don't pass validation. By default, 3.</td></tr>
  <tr><td>SCORE_RBL_ERR</td><td>Points subtracted if server sending IP is listed in one or more RBL. By default, 1.5.</td></tr>
</table>

\* Only mandatory if using the installer script.

## Acknowledgements and Licenses

This project wouldn't be possible without these amazing packages :heart: :

- aiosmtpd
  - License: [Apache 2.0](https://github.com/aio-libs/aiosmtpd/blob/master/LICENSE)
  - Repo: https://github.com/aio-libs/aiosmtpd/ 
- pymysql
  - License: [MIT License](https://github.com/PyMySQL/PyMySQL/blob/main/LICENSE)
  - Repo: https://github.com/PyMySQL/PyMySQL
- dkimpy
  - License: [zlib](https://git.launchpad.net/dkimpy/tree/LICENSE)
  - Repo: https://launchpad.net/dkimpy
- dnspython
  - License: [ISC License](https://github.com/rthalley/dnspython/blob/main/LICENSE)
  - Repo: https://github.com/rthalley/dnspython
- uuid_utils
  - License: [BSD 3-Clause](https://github.com/aminalaee/uuid-utils/blob/main/LICENSE.md)
  - Repo: https://github.com/aminalaee/uuid-utils
- python-dotenv
  - License: [BSD 3-Clause](https://github.com/theskumar/python-dotenv/blob/main/LICENSE)
  - Repo: https://github.com/theskumar/python-dotenv 
- cryptography
  - License: [APACHE|BSD](https://github.com/pyca/cryptography/blob/main/LICENSE)
  - Repo: https://github.com/pyca/cryptography
- checkdmarc
  - License: [Apache 2.0](https://github.com/domainaware/checkdmarc/blob/master/LICENSE)
  - Repo: https://github.com/domainaware/checkdmarc