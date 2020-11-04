#!/bin/bash

cd /srv/www/ponytracker

source env/bin/activate
export DJANGO_SETTINGS_MODULE=ponytracker.local_settings

cd ponytracker

celery -A ponytracker worker -l INFO -B
