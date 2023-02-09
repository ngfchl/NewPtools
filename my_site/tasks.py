import logging
import time

from celery import shared_task

logger = logging.getLogger('ptools')


@shared_task
def send_sms(mobile):
    print('任务开始')
    for i in range(5):
        time.sleep(1)
        print(i)
    print(mobile)
    print('任务结束')
    return 'ok'
