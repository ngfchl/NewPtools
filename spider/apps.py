from django.apps import AppConfig


class SpiderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'spider'
    verbose_name = '爬虫模块'
