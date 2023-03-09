import logging
from typing import List

import pytz
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from ninja import Router

from schedule.models import Task
from schedule.schema import TaskSchemaOut, CrontabTaskSchemaIn, PeriodicTaskSchemaOut
from toolbox.schema import CommonResponse

# Create your views here.
logger = logging.getLogger('ptools')
router = Router(tags=['schedule'])


@router.get('/schedules', response=CommonResponse[List[TaskSchemaOut]], description='定时列表')
def get_schedule_list(request):
    data = [{'task': task, 'desc': desc} for (task, desc) in Task.choices]
    return CommonResponse.success(data=data)


@router.get('/crontab', response=CommonResponse[List[PeriodicTaskSchemaOut]], description='定时列表')
def get_crontab_schedule_list(request):
    data = PeriodicTask.objects.all()
    return CommonResponse.success(data=list(data))


@router.post('/add', response=CommonResponse, description='我的站点-列表')
def add_crontab_schedule(request, task: CrontabTaskSchemaIn):
    # 创建一个时间调度器
    # schedule, _ = IntervalSchedule.objects.get_or_create(
    #     every=10,
    #     period=IntervalSchedule.SECONDS
    # )
    # 创建一个时间调度任务,无args即为无参数任务
    # PeriodicTask.objects.create(
    #     interval=schedule,  # 调度方式
    #     name='',
    #     task='schedule.tasks.*',
    #     # args=json.dumps('args')
    # )
    # times = '0 4 * * *'
    # params = ['minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year']
    # crontab = {param: time for time, param in zip(times.split(' '), params)}
    time_zone = pytz.timezone('Asia/Shanghai')
    cron_schedule, _ = CrontabSchedule.objects.get_or_create(task.crontab, timezone=time_zone)
    periodic_task = PeriodicTask.objects.create(
        crontab=cron_schedule,
        name=task.name,
        task=task.task
    )
    logger.info(periodic_task)
    return CommonResponse.success(msg=f'{periodic_task.name} 任务创建成功！')
