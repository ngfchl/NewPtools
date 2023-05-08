import logging
import traceback
from typing import List

import pytz
from django.core.exceptions import ValidationError
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from ninja import Router

from schedule.models import Task
from schedule.schema import TaskSchemaOut, CrontabTaskSchemaIn, PeriodicTaskSchemaOut, CrontabSchemaOut
from toolbox.schema import CommonResponse

# Create your views here.
logger = logging.getLogger('ptools')
router = Router(tags=['schedule'])


@router.get('/tasks', response=CommonResponse[List[TaskSchemaOut]], description='任务列表')
def get_schedule_list(request):
    data = [{'task': task, 'desc': desc} for (task, desc) in Task.choices]
    return CommonResponse.success(data=data)


@router.get('/schedules', response=CommonResponse[List[PeriodicTaskSchemaOut]], description='自动任务列表')
def get_crontab_schedule_list(request):
    data = PeriodicTask.objects.all()
    return CommonResponse.success(data=list(data))


@router.get('/crontabs', response=CommonResponse[List[CrontabSchemaOut]], description='crontab列表')
def get_crontab_list(request):
    data = CrontabSchedule.objects.all()
    return CommonResponse.success(data=list(data))


@router.post('/schedule', response=CommonResponse, description='添加计划任务')
def add_crontab_schedule(request, task: CrontabTaskSchemaIn):
    time_zone = pytz.timezone('Asia/Shanghai')
    try:
        cron_schedule, _ = CrontabSchedule.objects.get_or_create(
            defaults=task.crontab.dict(),
            timezone=time_zone,
            hour=task.crontab.hour,
            minute=task.crontab.minute,
        )
        periodic_task = PeriodicTask.objects.create(
            crontab=cron_schedule,
            name=task.name,
            task=task.task,
            args=task.args,
            kwargs=task.kwargs,
        )
        logger.info(periodic_task)
        return CommonResponse.success(msg=f'{periodic_task.name} 任务创建成功！')
    except ValidationError as e:
        return CommonResponse.error(msg=f'{task.name} 任务已存在!')
    except Exception as e:
        logger.info(traceback.format_exc(3))
        return CommonResponse.error(msg=f'{task.name} 任务创建失败!')


@router.get('/schedule', response=CommonResponse[PeriodicTaskSchemaOut], description='修改计划任务')
def get_crontab_schedule(request, schedule_id: int):
    time_zone = pytz.timezone('Asia/Shanghai')
    periodic_task = PeriodicTask.objects.get(id=schedule_id)
    logger.info(periodic_task)
    return CommonResponse.success(data=periodic_task)


@router.delete('/schedule', response=CommonResponse, description='删除计划任务')
def delete_crontab_schedule(request, schedule_id: int):
    time_zone = pytz.timezone('Asia/Shanghai')
    periodic_task = PeriodicTask.objects.get(id=schedule_id)
    try:
        periodic_task.delete()
        logger.info(periodic_task)
        return CommonResponse.success(msg=f'任务 {periodic_task.name} 删除成功！')
    except Exception as e:
        logger.info(traceback.format_exc(3))
        return CommonResponse.error(msg=f'任务 {periodic_task.name} 删除失败!')


@router.put('/schedule', response=CommonResponse, description='修改计划任务')
def edit_crontab_schedule(request, task: CrontabTaskSchemaIn):
    time_zone = pytz.timezone('Asia/Shanghai')
    periodic_task = PeriodicTask.objects.get(id=task.id)
    if isinstance(task.crontab, dict):
        cron_schedule, _ = CrontabSchedule.objects.get_or_create(
            defaults=task.crontab.dict(),
            timezone=time_zone,
            hour=task.crontab.hour,
            minute=task.crontab.minute,
        )
        periodic_task.crontab = cron_schedule
    periodic_task.name = task.name
    periodic_task.task = task.task
    periodic_task.enabled = task.enabled
    periodic_task.save()
    logger.info(periodic_task)
    return CommonResponse.success(msg=f'{periodic_task.name} 任务修改成功!')
