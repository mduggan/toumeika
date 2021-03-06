#!/usr/bin/env bash

apt-get update
apt-get upgrade -y
apt-get install -y python-pip optipng imagemagick poppler-utils git sqlite3

apt-get install -y apache2 libapache2-mod-wsgi

# requirements for lxml
apt-get install -y python-dev libxml2-dev zlib1g-dev libxslt1-dev

# for compiling tesseract:
apt-get install -y libtiff5 libtiff5-dev liblept4 libleptonica-dev

# for running from postgres
apt-get install -y postgresql postgresql-client

pip install -U pip
pip install -r requirements.txt


sudo a2enmod expires
sudo a2enmod rewrite
sudo a2ensite toumeika.conf
