import os

import django
from celery import Celery
from django.conf import settings

celery_app = Celery('auxiliary')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auxiliary.settings")
django.setup()
celery_app.config_from_object("auxiliary:settings")
celery_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
