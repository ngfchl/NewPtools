from django.db import models

from auxiliary.base import BaseEntity


# Create your models here.

class PushConfig(models.TextChoices):
    # date = 'date', '单次任务'
    wechat_work_push = 'wechat_work_push', '企业微信通知'
    wxpusher_push = 'wxpusher_push', 'WxPusher通知'
    pushdeer_push = 'pushdeer_push', 'PushDeer通知'
    bark_push = 'bark_push', 'Bark通知'
    iyuu_push = 'iyuu_push', '爱语飞飞'
    telegram_push = 'telegram_push', 'Telegram通知'
