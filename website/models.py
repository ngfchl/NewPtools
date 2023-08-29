from django.db import models

from auxiliary.base import BaseEntity


# Create your models here.


class WebSite(BaseEntity):
    """    站点基本信息及信息抓取规则    """
    # 基本信息
    url = models.URLField(verbose_name='站点网址', default='', help_text='请保留网址结尾的"/"', unique=True)
    name = models.CharField(max_length=32, verbose_name='站点名称')
    nickname = models.CharField(max_length=16, verbose_name='站点简称', default='', help_text='英文，用于刷流')
    logo = models.URLField(verbose_name='站点logo', default='favico.ico', help_text='站点logo图标')
    tracker = models.CharField(verbose_name='tracker', default='', help_text='tracker网址关键字', max_length=256)
    sp_full = models.FloatField(verbose_name='满魔', default=107, help_text='站点满时魔')
    limit_speed = models.IntegerField(verbose_name='上传速度限制',
                                      default=100,
                                      help_text='单种限速，单位：MB/S')
    tags = models.CharField(verbose_name='站点标签', default='电影,电视剧', max_length=128,
                            help_text='站点资源类型，以`,`分割')
    iyuu = models.IntegerField(verbose_name='iyuu', default=0)
    # 功能支持
    sign_in = models.BooleanField(verbose_name="签到支持", default=True)
    get_info = models.BooleanField(verbose_name="站点数据", default=True)
    repeat_torrents = models.BooleanField(verbose_name="辅种支持", default=False)
    brush_free = models.BooleanField(verbose_name="Free刷流", default=True)
    brush_rss = models.BooleanField(verbose_name="RSS刷流", default=False)
    hr_discern = models.BooleanField(verbose_name="HR识别", default=False)
    search_torrents = models.BooleanField(verbose_name="搜索支持", default=False)

    # 主要页面
    page_index = models.CharField(verbose_name='首页', default='index.php', max_length=64)
    page_torrents = models.CharField(verbose_name='默认搜索页面', default='torrents.php?incldead=1', max_length=64)
    page_sign_in = models.CharField(verbose_name='默认签到链接', default='attendance.php', max_length=64)
    page_control_panel = models.CharField(verbose_name='控制面板', default='usercp.php', max_length=64)
    page_detail = models.CharField(verbose_name='详情页面链接', default='details.php?id={}', max_length=64)
    page_download = models.CharField(verbose_name='默认下载链接', default='download.php?id={}', max_length=64)
    page_user = models.CharField(verbose_name='用户信息链接', default='userdetails.php?id={}', max_length=64)
    page_search = models.CharField(verbose_name='搜索链接', default='torrents.php?incldead=1&search={}', max_length=64)
    page_message = models.CharField(verbose_name='消息页面', default='messages.php', max_length=64)
    page_hr = models.CharField(verbose_name='HR考核页面', default='myhr.php?hrtype=1&userid={}', max_length=64)
    page_leeching = models.CharField(verbose_name='当前下载信息',
                                     default='getusertorrentlistajax.php?userid={}&type=leeching',
                                     max_length=64)
    page_uploaded = models.CharField(verbose_name='发布种子信息',
                                     default='getusertorrentlistajax.php?userid={}&type=uploaded',
                                     max_length=64)
    page_seeding = models.CharField(verbose_name='当前做种信息',
                                    default='getusertorrentlistajax.php?userid={}&type=seeding',
                                    max_length=64)
    page_completed = models.CharField(verbose_name='完成种子信息',
                                      default='getusertorrentlistajax.php?userid={}&type=completed',
                                      max_length=64)
    page_mybonus = models.CharField(verbose_name='魔力值页面',
                                    default='mybonus.php',
                                    max_length=64)
    page_viewfilelist = models.CharField(verbose_name='文件列表链接',
                                         default='viewfilelist.php?id={}',
                                         max_length=64)
    # 签到信息
    sign_info_title = models.CharField(verbose_name='签到消息标题',
                                       default='//td[@id="outer"]//td[@class="embedded"]/h2/text()',
                                       help_text='签到页面消息标题',
                                       max_length=128)
    sign_info_content = models.CharField(verbose_name='签到消息内容',
                                         default='//td[@id="outer"]//td[@class="embedded"]/table//td//text()',
                                         help_text='签到页面消息内容',
                                         max_length=128)
    # HR及其他
    hr = models.BooleanField(verbose_name='H&R', default=False, help_text='站点是否开启HR')
    hr_rate = models.IntegerField(verbose_name='HR分享率', default=2, help_text='站点要求HR种子的分享率，最小：1')
    hr_time = models.IntegerField(verbose_name='HR时间', default=10, help_text='站点要求HR种子最短做种时间，单位：小时')

    # 状态信息XPath
    my_invitation_rule = models.CharField(
        verbose_name='邀请资格',
        default='//span/a[contains(@href,"invite.php?id=")]/following-sibling::text()[1]',
        max_length=128)
    my_time_join_rule = models.CharField(
        verbose_name='注册时间',
        default='//td[contains(text(),"加入")]/following-sibling::td/span/@title',
        max_length=128)
    my_latest_active_rule = models.CharField(
        verbose_name='最后活动时间',
        default='//td[contains(text(),"最近动向")]/following-sibling::td/span/@title',
        max_length=128)
    my_uploaded_rule = models.CharField(
        verbose_name='上传量',
        default='//font[@class="color_uploaded"]/following-sibling::text()[1]',
        max_length=128)
    my_downloaded_rule = models.CharField(
        verbose_name='下载量',
        default='//font[@class="color_downloaded"]/following-sibling::text()[1]',
        max_length=128)
    my_ratio_rule = models.CharField(
        verbose_name='分享率',
        default='//font[@class="color_ratio"][1]/following-sibling::text()[1]',
        max_length=128)
    my_bonus_rule = models.CharField(
        verbose_name='魔力值',
        default='//a[@href="mybonus.php"]/following-sibling::text()[1]',
        max_length=128)
    my_per_hour_bonus_rule = models.CharField(
        verbose_name='时魔',
        default='//div[contains(text(),"每小时能获取")]/text()[1]',
        max_length=128)
    my_score_rule = models.CharField(
        verbose_name='保种积分',
        default='//font[@class="color_bonus" and contains(text(),"积分")]/following-sibling::text()[1]',
        max_length=128)
    my_level_rule = models.CharField(
        verbose_name='用户等级',
        default='//table[@id="info_block"]//span/a[contains(@class,"_Name") and contains(@href,"userdetails.php?id=")]/@class',
        max_length=128
    )
    my_passkey_rule = models.CharField(
        verbose_name='Passkey',
        default='//td[contains(text(),"密钥")]/following-sibling::td[1]/text()',
        max_length=128
    )
    my_uid_rule = models.CharField(
        verbose_name='用户ID',
        default='//table[@id="info_block"]//span/a[contains(@class,"_Name") and contains(@href,"userdetails.php?id=")]/@href',
        max_length=128
    )
    my_hr_rule = models.CharField(
        verbose_name='H&R',
        default='//a[@href="myhr.php"]//text()',
        max_length=128)
    my_leech_rule = models.CharField(
        verbose_name='下载数量',
        default='//img[@class="arrowdown"]/following-sibling::text()[1]',
        max_length=128)

    my_publish_rule = models.CharField(verbose_name='发种数量',
                                       default='//p/preceding-sibling::b/text()[1]',
                                       max_length=128)

    my_seed_rule = models.CharField(verbose_name='做种数量',
                                    default='//img[@class="arrowup"]/following-sibling::text()[1]',
                                    max_length=128)

    my_seed_vol_rule = models.CharField(verbose_name='做种大小',
                                        default='//tr/td[3]',
                                        help_text='需对数据做处理',
                                        max_length=128)
    my_mailbox_rule = models.CharField(verbose_name='邮件规则',
                                       default='//a[@href="messages.php"]/font[contains(text(),"条")]/text()[1]',
                                       help_text='获取新邮件',
                                       max_length=128)
    my_message_title = models.CharField(verbose_name='邮件标题',
                                        default='//img[@alt="Unread"]/parent::td/following-sibling::td/a[1]//text()',
                                        help_text='获取邮件标题',
                                        max_length=128)
    my_notice_rule = models.CharField(verbose_name='公告规则',
                                      default='//a[@href="index.php"]/font[contains(text(),"条")]/text()[1]',
                                      help_text='获取新公告',
                                      max_length=128)
    my_notice_title = models.CharField(verbose_name='公告标题',
                                       default='//td[@class="text"]/div/a//text()',
                                       help_text='获取公告标题',
                                       max_length=128)
    my_notice_content = models.CharField(verbose_name='公告内容',
                                         default='//td[@class="text"]/div/a/following-sibling::div',
                                         help_text='获取公告内容',
                                         max_length=128)
    # 列表页XPATH
    torrents_rule = models.CharField(verbose_name='种子列表',
                                     default='//table[@class="torrents"]/tr',
                                     max_length=128)
    torrent_title_rule = models.CharField(verbose_name='种子名称',
                                          default='.//td[@class="embedded"]/a/b/text()',
                                          max_length=128)
    torrent_subtitle_rule = models.CharField(
        verbose_name='小标题',
        default='.//a[contains(@href,"detail")]/parent::td/text()[last()]',
        max_length=128)
    torrent_tags_rule = models.CharField(
        verbose_name='种子标签',
        default='.//a[contains(@href,"detail")]/../span[contains(@style,"background-color")]/text()',
        max_length=128)
    torrent_detail_url_rule = models.CharField(
        verbose_name='种子详情',
        default='.//td[@class="embedded"]/a[contains(@href,"detail")]/@href',
        max_length=128)
    torrent_category_rule = models.CharField(
        verbose_name='分类',
        default='.//td[@class="rowfollow nowrap"][1]/a[1]/img/@title',
        max_length=128)
    torrent_poster_rule = models.CharField(
        verbose_name='海报',
        default='.//table/tr/td[1]/img/@src',
        max_length=128)
    torrent_magnet_url_rule = models.CharField(
        verbose_name='主页下载链接',
        default='.//td/a[contains(@href,"download.php?id=")]/@href',
        max_length=128)
    torrent_size_rule = models.CharField(verbose_name='文件大小',
                                         default='.//td[5]/text()',
                                         max_length=128)
    torrent_hr_rule = models.CharField(
        verbose_name='H&R',
        default='.//table/tr/td/img[@class="hitandrun"]/@title',
        max_length=128)
    torrent_sale_rule = models.CharField(
        verbose_name='促销信息',
        default='.//img[contains(@class,"free")]/@alt',
        max_length=128
    )
    torrent_sale_expire_rule = models.CharField(
        verbose_name='促销时间',
        default='.//img[contains(@class,"free")]/following-sibling::font/span/@title',
        max_length=128)
    torrent_release_rule = models.CharField(
        verbose_name='发布时间',
        default='.//td[4]/span/@title',
        max_length=128)
    torrent_seeders_rule = models.CharField(
        verbose_name='做种人数',
        default='.//a[contains(@href,"#seeders")]/text()',
        max_length=128)
    torrent_leechers_rule = models.CharField(
        verbose_name='下载人数',
        default='.//a[contains(@href,"#leechers")]/text()',
        max_length=128)
    torrent_completers_rule = models.CharField(
        verbose_name='完成人数',
        default='.//a[contains(@href,"viewsnatches")]//text()',
        max_length=128)
    # 详情页种子信息
    detail_title_rule = models.CharField(
        verbose_name='详情页种子标题',
        default='//h1/text()[1]',
        max_length=128)
    detail_subtitle_rule = models.CharField(
        verbose_name='详情页种子副标题',
        default='//td[contains(text(),"副标题")]/following-sibling::td/text()[1]',
        max_length=128)
    detail_download_url_rule = models.CharField(
        verbose_name='详情页种子链接',
        default='//td[contains(text(),"种子链接")]/following-sibling::td/a/@href',
        max_length=128)
    detail_tags_rule = models.CharField(
        verbose_name='详情页标签',
        default='//td[contains(text(),"标签")]/following-sibling::td//text()',
        max_length=128)
    detail_size_rule = models.CharField(
        verbose_name='详情页种子大小',
        default='//td//b[contains(text(),"大小")]/following::text()[1]',
        max_length=128)
    detail_category_rule = models.CharField(
        verbose_name='详情页种子类型',
        default='//td/b[contains(text(),"类型")]/following-sibling::text()[1]',
        max_length=128)
    detail_poster_rule = models.CharField(
        verbose_name='详情页海报',
        default='//td/a/span[contains(text(),"简介")]/parent::a/parent::td/following-sibling::td//img[1]',
        max_length=128)
    detail_count_files_rule = models.CharField(
        verbose_name='详情页文件数',
        default='//td/b[contains(text(),"文件数")]/following-sibling::text()[1]',
        max_length=128)
    # HASH RULE
    detail_hash_rule = models.CharField(
        verbose_name='详情页种子HASH',
        default='//td/b[contains(text(),"Hash")]/following-sibling::text()[1]',
        max_length=128)
    detail_free_rule = models.CharField(
        verbose_name='详情页促销标记',
        default='//h1/b/font/@class',
        max_length=128)
    detail_free_expire_rule = models.CharField(
        verbose_name='详情页促销时间',
        default='//h1/font/span/@title',
        max_length=128)
    detail_douban_rule = models.CharField(
        verbose_name='详情页豆瓣信息',
        default='//td/a[starts-with(@href,"https://movie.douban.com/subject/")][1]',
        max_length=128)
    detail_imdb_rule = models.CharField(
        verbose_name='IMDB',
        default='//a[@class="faqlink" and starts-with(@href,"https://www.imdb.com/title/")]/@href',
        max_length=128)
    detail_hr_rule = models.CharField(
        verbose_name='H&R',
        default='//h1/img[@class="hitandrun"]/@title',
        max_length=128)

    class Meta:
        verbose_name = '站点信息'
        verbose_name_plural = verbose_name
        ordering = ['name', ]

    def __str__(self):
        return self.name


class UserLevelRule(BaseEntity):
    """    用户等级升级信息表    """
    site = models.ForeignKey(verbose_name='站 点', to=WebSite, to_field='id', on_delete=models.CASCADE)
    level_id = models.IntegerField(verbose_name='等级id', default=1)
    level = models.CharField(verbose_name='等 级', default='User', max_length=24, help_text='请去除空格')
    days = models.IntegerField(verbose_name='时 间', default=0, help_text='原样输入，单位：周')
    uploaded = models.CharField(verbose_name='上 传', default=0, help_text='原样输入，例：50GB，1.5TB', max_length=12)
    downloaded = models.CharField(verbose_name='下 载', default=0, help_text='原样输入，例：50GB，1.5TB', max_length=12)
    bonus = models.FloatField(verbose_name='魔 力', default=0)
    score = models.IntegerField(verbose_name='积 分', default=0)
    ratio = models.FloatField(verbose_name='分享率', default=0)
    torrents = models.IntegerField(verbose_name='发 种', help_text='发布种子数', default=0)
    leeches = models.IntegerField(verbose_name='吸血数', help_text='完成种子数', default=0)
    seeding_delta = models.FloatField(verbose_name='做种时间', help_text='累计做种时间', default=0)
    keep_account = models.BooleanField(verbose_name='保 号', default=False)
    graduation = models.BooleanField(verbose_name='毕 业', default=False)
    rights = models.TextField(verbose_name='权 利', help_text='当前等级所享有的权利与义务',
                              default='无')

    def __str__(self):
        return f'{self.site.nickname}/{self.level}'

    class Meta:
        unique_together = ('site', 'level_id', 'level',)
        verbose_name = '升级进度'
        verbose_name_plural = verbose_name
