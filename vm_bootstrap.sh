#!/usr/bin/env bash

apt-get update
apt-get upgrade -y
apt-get install -y python-pip

pip install -U pip

echo `which pip`
/usr/local/bin/pip install -r /vagrant/requirements.txt
