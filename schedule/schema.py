from django_celery_beat.models import PeriodicTask
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


class CrontabTaskSchemaIn(Schema):
    """cron任务"""
    name: str
    task: str
    crontab: CrontabSchemaIn


class PeriodicTaskSchemaOut(ModelSchema):
    class Config:
        model = PeriodicTask
        model_exclude = [
            'interval',
        ]
