from typing import Union, Optional

from django_celery_beat.models import PeriodicTask, CrontabSchedule, cronexp
from ninja import Schema, ModelSchema


class TaskSchemaOut(Schema):
    """任务及描述"""
    task: str
    desc: str


class CrontabSchemaIn(Schema):
    """cron表达式"""
    minute: str
    hour: str
    day_of_week: str = '*'
    day_of_month: str = '*'
    month_of_year: str = '*'


class CrontabSchemaOut(ModelSchema):
    express: str

    class Config:
        model = CrontabSchedule
        model_exclude = ['timezone']

    def resolve_express(self, obj):
        return '{} {} {} {} {}'.format(
            cronexp(self.minute), cronexp(self.hour),
            cronexp(self.day_of_month), cronexp(self.month_of_year),
            cronexp(self.day_of_week),
        )


class TaskEditSchemaIn(Schema):
    """cron任务"""
    id: int


class CrontabTaskSchemaIn(Schema):
    """cron任务"""
    id: int
    name: str
    task: str
    enabled: Optional[bool]
    crontab: Union[CrontabSchemaIn, int]


class PeriodicTaskSchemaOut(ModelSchema):
    class Config:
        model = PeriodicTask
        model_fields = [
            'id',
            'name',
            'task',
            'crontab',
            'one_off',
            'enabled',
            'last_run_at',
            'total_run_count',
            'description',
            'date_changed',
        ]
