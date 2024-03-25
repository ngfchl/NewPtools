from datetime import datetime

from django.db import models
from django.db.models import ManyToManyField, DateTimeField

from auxiliary.base import BaseEntity
from download.models import Downloader
from website.models import WebSite


# Create your models here.

class MySite(BaseEntity):
    # site = models.OneToOneField(verbose_name='站点', to=WebSite, on_delete=models.CASCADE)
    site = models.IntegerField(verbose_name='站点', unique=True)
    nickname = models.CharField(verbose_name='站点昵称', max_length=16, default=' ')
    sort_id = models.IntegerField(verbose_name='排序', default=1)
    # 用户信息
    user_id = models.CharField(verbose_name='用户ID', max_length=16,
                               help_text='请填写<font color="orangered">数字UID</font>，'
                                         '<font color="orange">* az,cz,ez,莫妮卡、普斯特请填写用户名</font>')
    passkey = models.CharField(max_length=128, verbose_name='PassKey', blank=True, null=True)
    api_key = models.CharField(max_length=128, verbose_name='ApiKey', blank=True, null=True)
    cookie = models.TextField(verbose_name='COOKIE', help_text='与UA搭配使用效果更佳，请和UA在同一浏览器提取')
    user_agent = models.TextField(verbose_name='User-Agent', help_text='请填写你获取cookie的浏览器的User-Agent',
                                  default='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                                          '(KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36 Edg/106.0.1370.42')
    rss = models.URLField(verbose_name='RSS地址', null=True, blank=True, help_text='RSS链接')
    torrents = models.CharField(verbose_name='种子地址', null=True, blank=True, help_text='免费种子链接',
                                max_length=512)
    # 用户设置
    sign_in = models.BooleanField(verbose_name='开启签到', default=True, help_text='是否开启签到')
    get_info = models.BooleanField(verbose_name='抓取信息', default=True, help_text='是否抓取站点数据')
    repeat_torrents = models.BooleanField(verbose_name="辅种支持", default=False)
    brush_free = models.BooleanField(verbose_name="Free刷流", default=True)
    brush_rss = models.BooleanField(verbose_name="RSS刷流", default=False, help_text="硬刚刷流")
    package_file = models.BooleanField(verbose_name="拆包刷流", default=False,
                                       help_text="拆包刷流，只下载一部分，针对大包小硬盘")
    hr_discern = models.BooleanField(verbose_name='开启HR下载', default=False, help_text='是否下载HR种子')
    search_torrents = models.BooleanField(verbose_name='开启搜索', default=True, help_text='是否开启搜索')
    custom_server = models.URLField(verbose_name='代理服务器', null=True, blank=True, help_text='部分站点需要')
    downloader = models.ForeignKey(verbose_name='下载服务器', null=True, blank=True, on_delete=models.SET_NULL,
                                   to=Downloader)
    remove_torrent_rules = models.TextField(verbose_name='刷流删种', null=True, blank=True,
                                            help_text='详细内容请查看文档')
    mirror = models.URLField(verbose_name='镜像网址', null=True, blank=True, help_text='必须带最后的 /')
    mirror_switch = models.BooleanField(verbose_name='镜像开关', default=False)
    # 用户数据 自动拉取
    time_join = models.DateTimeField(verbose_name='注册时间',
                                     default=datetime(2023, 1, 1, 12, 30, 00),
                                     help_text='请务必填写此项！')

    def __str__(self):
        return self.nickname

    class Meta:
        verbose_name = '我的站点'
        verbose_name_plural = verbose_name
        db_table = 'my_site_mysite'


# 站点信息
class SiteStatus(BaseEntity):
    # 获取日期，只保留当天最新数据
    site = models.ForeignKey(verbose_name='站点名称', to=MySite, on_delete=models.CASCADE)
    # 签到，有签到功能的访问签到页面，无签到的访问个人主页
    uploaded = models.BigIntegerField(verbose_name='上传量', default=0)
    downloaded = models.BigIntegerField(verbose_name='下载量', default=0)
    ratio = models.FloatField(verbose_name='分享率', default=0)
    my_bonus = models.FloatField(verbose_name='魔力值', default=0)
    my_score = models.FloatField(verbose_name='做种积分', default=0)
    seed_volume = models.BigIntegerField(verbose_name='做种体积', default=0)
    seed_days = models.IntegerField(verbose_name='做种时间', default=0)
    leech = models.IntegerField(verbose_name='当前下载', default=0)
    seed = models.IntegerField(verbose_name='当前做种', default=0)
    bonus_hour = models.FloatField(verbose_name='时魔', default=0)
    publish = models.IntegerField(verbose_name='发布种子', default=0)
    invitation = models.IntegerField(verbose_name='邀请资格', default=0)
    my_level = models.CharField(verbose_name='用户等级', max_length=32, default='')
    my_hr = models.CharField(verbose_name='H&R', max_length=32, default='')
    mail = models.IntegerField(verbose_name='新邮件', default=0)

    class Meta:
        verbose_name = '我的数据'
        verbose_name_plural = verbose_name
        db_table = 'my_site_sitestatus'

    def __str__(self):
        return self.site.nickname


class SignIn(BaseEntity):
    site = models.ForeignKey(verbose_name='站点名称', to=MySite, on_delete=models.CASCADE)
    sign_in_today = models.BooleanField(verbose_name='签到', default=False)
    sign_in_info = models.TextField(verbose_name='信息', default='')

    class Meta:
        verbose_name = '签到'
        verbose_name_plural = verbose_name
        db_table = 'my_site_signin'

    def __str__(self):
        return self.site.nickname


# 种子信息
class TorrentInfo(BaseEntity):
    site = models.ForeignKey(to=MySite, to_field='site', on_delete=models.CASCADE, verbose_name='所属站点', null=True)
    tid = models.IntegerField(verbose_name='种子ID')
    title = models.CharField(max_length=256, verbose_name='种子名称', default='')
    subtitle = models.CharField(max_length=256, verbose_name='标题', default='')
    category = models.CharField(max_length=128, verbose_name='分类', default='')
    magnet_url = models.URLField(verbose_name='下载链接', default='')
    tags = models.CharField(max_length=64, verbose_name='种子标签', default='')
    size = models.BigIntegerField(verbose_name='文件大小', default=0)
    hr = models.BooleanField(verbose_name='H&R考核', default=True, help_text='绿色为通过或无需HR考核')
    sale_status = models.CharField(verbose_name='优惠状态', default='', max_length=16)
    sale_expire = models.DateTimeField(verbose_name='到期时间', blank=True, null=True, )
    published = models.DateTimeField(verbose_name='发布时间', blank=True, null=True)
    seeders = models.IntegerField(verbose_name='做种人数', default=0, )
    leechers = models.IntegerField(verbose_name='下载人数', default=0, )
    completers = models.IntegerField(verbose_name='完成人数', default=0, )
    hash_string = models.CharField(max_length=128, verbose_name='Info_Hash', default='')
    filelist = models.CharField(max_length=128, verbose_name='文件列表', default='')
    douban_url = models.URLField(verbose_name='豆瓣链接', default='')
    imdb_url = models.URLField(verbose_name='imdb', default='')
    poster = models.URLField(verbose_name='海报', default='')
    files_count = models.IntegerField(verbose_name='文件数目', default=0)
    completed = models.IntegerField(verbose_name='已下载', default=0)
    uploaded = models.IntegerField(verbose_name='已上传', default=0)
    pieces_qb = models.CharField(verbose_name='pieces_qb', default='', max_length=128)
    pieces_tr = models.CharField(verbose_name='pieces_tr', default='', max_length=128)
    state = models.IntegerField(verbose_name='推送状态', default=0)
    downloader = models.ForeignKey(to=Downloader,
                                   on_delete=models.SET_NULL,
                                   verbose_name='下载器',
                                   blank=True, null=True)
    pushed = models.BooleanField(verbose_name='推送至服务器', default=False, help_text='推送至辅种服务器')

    class Meta:
        verbose_name = '种子管理'
        verbose_name_plural = verbose_name
        unique_together = ('site', 'tid')

    def __str__(self):
        return self.title

    def to_dict(self, fields=None, exclude=None):
        data = {}
        for f in self._meta.fields:
            value = f.value_from_object(self)

            if fields and f.name not in fields:
                continue

            if exclude and f.name in exclude:
                continue

            if isinstance(f, ManyToManyField):
                value = [i.id for i in value] if self.pk else None

            if isinstance(f, DateTimeField):
                value = value.strftime('%Y-%m-%d %H:%M:%S') if value else None

            if f.name == 'site':
                data['site_id'] = self.site_id
            else:
                data[f.name] = value

        return data
