import os

from celery import Celery

from django.apps import apps
from django.conf import settings


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ponytracker.settings')

app = Celery('ponytracker')

app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
