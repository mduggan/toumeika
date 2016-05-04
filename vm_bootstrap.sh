#!/usr/bin/env bash

apt-get update
apt-get upgrade -y
apt-get install -y python-pip optipng imagemagick poppler-utils
# for compiling tesseract:
apt-get install -y libtiff5 libtiff5-dev liblept4 libleptonica-dev

pip install -U pip

echo `which pip`
/usr/local/bin/pip install -r /vagrant/requirements.txt
