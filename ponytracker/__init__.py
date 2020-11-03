from django.conf import settings
if settings.CELERY_ENABLED:
    from ponytracker.celeryapp import app as celery_app
