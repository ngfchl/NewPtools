from django.db import models

from auxiliary.base import BaseEntity


# Create your models here.
class BaiduOCR(BaseEntity):
    """
    corpid=企业ID，在管理后台获取
    corpsecret: 自建应用的Secret，每个自建应用里都有单独的secret
    agentid: 应用ID，在后台应用中获取
    app_id = '2695'
    api_key = 'TUoKvq3w1d'
    secret_key = 'XojLDC9s5qc'
    """
    name = models.CharField(verbose_name='OCR', default='百度OCR', editable=False, max_length=64)
    enable = models.BooleanField(verbose_name='启用', default=False)
    api_key = models.CharField(verbose_name='API-Key',
                               max_length=64,
                               null=True, blank=True)
    secret_key = models.CharField(verbose_name='Secret',
                                  max_length=64,
                                  help_text='应用的Secret',
                                  null=True, blank=True)
    app_id = models.CharField(verbose_name='应用ID',
                              max_length=64,
                              help_text='APP ID',
                              null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = '百度OCR'
        verbose_name_plural = verbose_name
