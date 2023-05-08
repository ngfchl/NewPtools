from __future__ import absolute_import

import os

# import django
from celery import Celery, Task

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auxiliary.settings")
# django.setup()
app = Celery('auxiliary')

app.config_from_object("django.conf:settings", namespace='CELERY')
# tasks_list = [f'auxiliary.{x}' for x in settings.INSTALLED_APPS]
# print(tasks_list)
app.autodiscover_tasks()


class BaseTask(Task):
    """
        celery 基类, 继承Task
    """

    def __call__(self, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return:
        """
        print('TASK STARTING: {0.name}[{0.request.id}]'.format(self))
        return super(BaseTask, self).__call__(*args, **kwargs)

    # 任务成功
    def on_success(self, retval, task_id, args, kwargs):
        print(self.request)
        print("success")
        print(retval)
        print(task_id)
        print(args)
        print(kwargs)

        return super(BaseTask, self).on_success(retval, task_id, args, kwargs)

    # 任务失败
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        print("failure")
        print(exc)
        print(task_id)
        print(args)
        print(kwargs)
        print(einfo)
        # 失败重试
        self.retry(exc=exc)

    # finally
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        print(status, retval, task_id, args, kwargs, einfo)
        print('task %s is finished' % self.name)
