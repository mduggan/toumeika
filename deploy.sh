#!/bin/bash
pybabel compile -d translations
sudo rsync -rav main.py templates translations static shikin /var/www/toumeika
sudo find /var/www/toumeika -name \*.pyo -delete
sudo find /var/www/toumeika -name \*.pyc -delete
sudo find /var/www/toumeika -name \*.py -exec pycompile -O {} +
sudo chown -R www-data /var/www/toumeika/db
sudo service apache2 reload
