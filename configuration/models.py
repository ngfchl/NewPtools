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


class Notify(BaseEntity):
    """
    corpid=企业ID，在管理后台获取
    corpsecret: 自建应用的Secret，每个自建应用里都有单独的secret
    agentid: 应用ID，在后台应用中获取
    touser: 接收者用户名(微信账号), 多个用户用 | 分割, 与发送消息的touser至少存在一个
    """
    name = models.CharField(verbose_name='通知方式', choices=PushConfig.choices,
                            default=PushConfig.wechat_work_push,
                            unique=True,
                            max_length=64)
    enable = models.BooleanField(verbose_name='开启通知', default=True, help_text='只有开启才能发送哦！')
    corpid = models.CharField(verbose_name='企业ID', max_length=64,
                              help_text='微信企业ID', null=True, blank=True)
    corpsecret = models.CharField(verbose_name='Secret', max_length=64,
                                  help_text='应用的Secret/Token', null=True, blank=True)
    agentid = models.CharField(verbose_name='应用ID', max_length=64,
                               help_text='APP ID', null=True, blank=True)

    touser = models.CharField(verbose_name='接收者', max_length=64,
                              help_text='接收者用户名/UID',
                              null=True, blank=True)
    custom_server = models.URLField(verbose_name='服务器', null=True, blank=True,
                                    help_text='IYuu与BARK请必填，详情参考教程！')

    def __str__(self):
        return self.get_name_display()

    class Meta:
        verbose_name = '通知推送'
        verbose_name_plural = verbose_name
