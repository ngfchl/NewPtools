from __future__ import absolute_import

import os

# import django
from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auxiliary.settings")
# django.setup()
app = Celery('auxiliary')

app.config_from_object("django.conf:settings", namespace='CELERY')
# tasks_list = [f'auxiliary.{x}' for x in settings.INSTALLED_APPS]
# print(tasks_list)
app.autodiscover_tasks()


@app.task
def add():
    return 0
