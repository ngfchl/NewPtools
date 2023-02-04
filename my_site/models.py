from datetime import datetime

from django.db import models

from auxiliary.base import BaseEntity
from website.models import WebSite


# Create your models here.

class MySite(BaseEntity):
    site = models.OneToOneField(verbose_name='站点', to=WebSite, on_delete=models.CASCADE)
    sort_id = models.IntegerField(verbose_name='排序', default=1)
    # 用户信息
    user_id = models.CharField(verbose_name='用户ID', max_length=16,
                               help_text='请填写<font color="orangered">数字UID</font>，'
                                         '<font color="orange">* az,cz,ez,莫妮卡、普斯特请填写用户名</font>')
    passkey = models.CharField(max_length=128, verbose_name='PassKey', blank=True, null=True)
    cookie = models.TextField(verbose_name='COOKIE', help_text='与UA搭配使用效果更佳，请和UA在同一浏览器提取')
    user_agent = models.TextField(verbose_name='User-Agent', help_text='请填写你获取cookie的浏览器的User-Agent',
                                  default='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                                          '(KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36 Edg/106.0.1370.42')
    # 用户设置
    hr = models.BooleanField(verbose_name='开启HR下载', default=False, help_text='是否下载HR种子')
    sign_in = models.BooleanField(verbose_name='开启签到', default=True, help_text='是否开启签到')
    get_info = models.BooleanField(verbose_name='抓取信息', default=True, help_text='是否抓取站点数据')
    search = models.BooleanField(verbose_name='开启搜索', default=True, help_text='是否开启搜索')
    # 用户数据 自动拉取
    time_join = models.DateTimeField(verbose_name='注册时间',
                                     default=datetime.strptime('2023-01-01 12:30:00', '%Y-%m-%d %H:%M:%S'),
                                     help_text='请务必填写此项！')

    def __str__(self):
        return self.site.name

    class Meta:
        verbose_name = '我的站点'
        verbose_name_plural = verbose_name
        db_table = 'my_site_mysite'


# 站点信息
class SiteStatus(BaseEntity):
    # 获取日期，只保留当天最新数据
    site = models.ForeignKey(verbose_name='站点名称', to=MySite, on_delete=models.CASCADE)
    # 签到，有签到功能的访问签到页面，无签到的访问个人主页
    uploaded = models.IntegerField(verbose_name='上传量', default=0)
    downloaded = models.IntegerField(verbose_name='下载量', default=0)
    ratio = models.FloatField(verbose_name='分享率', default=0)
    my_bonus = models.FloatField(verbose_name='魔力值', default=0)
    my_score = models.FloatField(verbose_name='做种积分', default=0)
    seed_volume = models.IntegerField(verbose_name='做种体积', default=0)
    seed_days = models.IntegerField(verbose_name='做种时间', default=0)
    leech = models.IntegerField(verbose_name='当前下载', default=0)
    seed = models.IntegerField(verbose_name='当前做种', default=0)
    bonus_hour = models.FloatField(verbose_name='时魔', default=0)
    publish = models.IntegerField(verbose_name='发布种子', default=0)
    invitation = models.IntegerField(verbose_name='邀请资格', default=0)
    my_level = models.CharField(verbose_name='用户等级', max_length=16, default='')
    my_hr = models.CharField(verbose_name='H&R', max_length=16, default='')
    mail = models.IntegerField(verbose_name='新邮件', default=0)

    class Meta:
        verbose_name = '我的数据'
        verbose_name_plural = verbose_name
        db_table = 'my_site_sitestatus'

    def __str__(self):
        return self.site.site.name


class SignIn(BaseEntity):
    site = models.ForeignKey(verbose_name='站点名称', to=MySite, on_delete=models.CASCADE)
    sign_in_today = models.BooleanField(verbose_name='签到', default=False)
    sign_in_info = models.CharField(verbose_name='信息', default='', max_length=256)

    class Meta:
        verbose_name = '签到'
        verbose_name_plural = verbose_name
        db_table = 'my_site_signin'

    def __str__(self):
        return self.site.site.name
