from django.apps import AppConfig


class MonkeyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monkey'
    verbose_name = '油猴助手'
