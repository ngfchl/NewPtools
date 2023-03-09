import logging

from django_celery_beat.models import IntervalSchedule, PeriodicTask
from ninja import Router

from schedule import tasks
from toolbox.schema import CommonResponse

# Create your views here.
logger = logging.getLogger('ptools')
router = Router(tags=['schedule'])


@router.get('/schedules', response=CommonResponse, description='定时列表')
def get_schedule_list(request):
    data = [{
        'task': f'schedule.tasks.{key}',
        'desc': getattr(tasks, key).__doc__.strip()
    } for key in dir(tasks) if key.startswith('auto_')]
    return CommonResponse.success(data=data)


@router.get('/mysite', response=CommonResponse, description='我的站点-列表')
def add_interval_schedule(request):
    # 创建一个时间调度器
    schedule, created = IntervalSchedule.objects.get_or_create(
        every=10,
        period=IntervalSchedule.SECONDS
    )
    # 创建一个无参数的时间调度任务
    PeriodicTask.objects.create(
        interval=schedule,  # 调度方式
        name='',
        task=''
    )
