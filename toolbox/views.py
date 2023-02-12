import json
import logging
import os
import re
import subprocess
import time
import traceback
from datetime import datetime

import aip
import cloudscraper
import dateutil.parser
import git
import requests
import toml as toml
from pypushdeer import PushDeer
from .wechat_push import WechatPush
from wxpusher import WxPusher

from auxiliary.base import PushConfig
from auxiliary.settings import BASE_DIR
from my_site.models import MySite, SiteStatus
from spider.views import PtSpider
from toolbox.models import BaiduOCR, Notify
from toolbox.schema import CommonResponse
from website.models import WebSite

# Create your views here.
logger = logging.getLogger('ptools')


def parse_toml(cmd) -> dict:
    """从配置文件解析获取相关项目"""
    data = toml.load('db/ptools.toml')
    return data.get(cmd)


def check_token(token) -> bool:
    own_token = parse_toml('token').get(token)
    return own_token == token


def cookie2dict(source_str: str) -> dict:
    """
    cookies字符串转为字典格式,传入参数必须为cookies字符串
    """
    dist_dict = {}
    list_mid = source_str.strip().split(';')
    for i in list_mid:
        # 以第一个选中的字符分割1次，
        if len(i) <= 0:
            continue
        list2 = i.split('=', 1)
        dist_dict[list2[0]] = list2[1]
    return dist_dict


# 获取字符串中的数字
get_decimals = lambda x: re.search("\d+(\.\d+)?", x).group() if re.search("\d+(\.\d+)?", x) else 0


class FileSizeConvert:
    """文件大小和字节数互转"""

    @staticmethod
    def parse_2_byte(file_size: str) -> int:
        if not file_size:
            return 0
        """将文件大小字符串解析为字节"""
        regex = re.compile(r'(\d+(?:\.\d+)?)\s*([kmgtp]?b)', re.IGNORECASE)

        order = ['b', 'kb', 'mb', 'gb', 'tb', 'pb', 'eb']

        for value, unit in regex.findall(file_size):
            return int(float(value) * (1024 ** order.index(unit.lower())))

    @staticmethod
    def parse_2_file_size(byte: int) -> str:
        if not byte:
            return '0B'
        units = ["B", "KB", "MB", "GB", "TB", "PB", 'EB']
        size = 1024.0
        for i in range(len(units)):
            if (byte / size) < 1:
                return "%.3f %s" % (byte, units[i])
            byte = byte / size


def baidu_ocr_captcha(img_url):
    """百度OCR高精度识别，传入图片URL"""
    # 获取百度识别结果
    ocr = BaiduOCR.objects.filter(enable=True).first()
    if not ocr:
        logger.error('未设置百度OCR文本识别API，无法使用本功能！')
        return CommonResponse.error(msg='未设置百度OCR文本识别API，无法使用本功能！')
    try:
        ocr_client = aip.AipOcr(appId=ocr.app_id, secretKey=ocr.secret_key, apiKey=ocr.api_key)
        res1 = ocr_client.basicGeneralUrl(img_url)
        logger.info(res1)
        if res1.get('error_code'):
            res1 = ocr_client.basicAccurateUrl(img_url)
        logger.info('res1: {}'.format(res1))
        if res1.get('error_code'):
            return CommonResponse.error(msg=res1.get('error_msg'))
        res2 = res1.get('words_result')[0].get('words')
        # 去除杂乱字符
        imagestring = ''.join(re.findall('[A-Za-z0-9]+', res2)).strip()
        logger_info = '百度OCR天空验证码：{}，长度：{}'.format(imagestring, len(imagestring))
        logger.info(logger_info)
        # 识别错误就重来

        return CommonResponse.success(data=imagestring)
    except Exception as e:
        msg = '百度OCR识别失败：{}'.format(e)
        logger.info(traceback.format_exc(limit=3))
        # raise
        # self.send_text(title='OCR识别出错咯', message=msg)
        return CommonResponse.error(msg=msg)


def parse_ptpp_cookies(data_list):
    # 解析前端传来的数据
    datas = json.loads(data_list.get('cookies'))
    info_list = json.loads(data_list.get('info'))
    userdata_list = json.loads(data_list.get('userdata'))
    cookies = []
    try:
        for data, info in zip(datas, info_list):
            cookie_list = data.get('cookies')
            host = data.get('host')
            cookie_str = ''
            for cookie in cookie_list:
                cookie_str += '{}={};'.format(cookie.get('name'), cookie.get('value'))
            # logger.info(domain + cookie_str)
            cookies.append({
                'url': data.get('url'),
                'host': host,
                'icon': info.get('icon'),
                'info': info.get('user'),
                'passkey': info.get('passkey'),
                'cookies': cookie_str.rstrip(';'),
                'userdatas': userdata_list.get(host)
            })
        logger.info('站点记录共{}条'.format(len(cookies)))
        # logger.info(cookies)
        return CommonResponse.success(data=cookies)
    except Exception as e:
        # raise
        # 打印异常详细信息
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg='Cookies解析失败，请确认导入了正确的cookies备份文件！{}'.format(e))


# @transaction.atomic
def get_uid_and_passkey(cookie: dict):
    url = cookie.get('url')
    host = cookie.get('host')
    site = WebSite.objects.filter(url__contains=host).first()
    # logger.info('查询站点信息：', site, site.url, url)
    if not site:
        return CommonResponse.error(msg='尚未支持此站点：{}'.format(url))
    # 如果有更新cookie，如果没有继续创建
    userdatas = cookie.get('userdatas')
    time_stamp = cookie.get('info').get('joinTime')
    if not time_stamp:
        time_join = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(time_stamp) / 1000))
    else:
        time_join = datetime.now()
    uid = cookie.get('info').get('id')
    if not uid:
        try:
            logger.info('备份文件未获取到User_id，尝试获取中')
            scraper = cloudscraper.create_scraper(browser={
                'browser': 'chrome',
                'platform': 'darwin',
            })
            response = scraper.get(
                url=site.url + site.page_index,
                cookies=cookie.get('cookies'),
            )
            logger.info(response.text)
            uid = ''.join(PtSpider.parse(site, response, site.my_uid_rule)).split('=')[-1]
            logger.info(f'uid:{uid}')
        except Exception as e:
            passkey_msg = f'{site.name} Uid获取失败，请手动添加！'
            msg = f'{site.name} 信息导入失败！ {passkey_msg}：{e}'
            logger.info(passkey_msg)
            return CommonResponse.error(
                msg=msg
            )
    result = MySite.objects.update_or_create(site=site.id, defaults={
        'cookie': cookie.get('cookies'),
        'user_id': uid,
        'time_join': time_join,
    })
    my_site = result[0]
    passkey_msg = ''
    logger.info('开始导入PTPP历史数据')
    for key, value in userdatas.items():
        logger.info(key)
        try:
            downloaded = value.get('downloaded')
            uploaded = value.get('uploaded')
            seeding_size = value.get('seedingSize')
            my_bonus = value.get('bonus')
            ratio = value.get('ratio')
            seed = value.get('seeding')
            my_level_str = value.get('levelName')
            if 'hdcity' in site.url:
                my_level = my_level_str.replace('[', '').replace(']', '').strip(" ").strip()
            else:
                my_level = re.sub(u"([^\u0041-\u005a\u0061-\u007a])", "", my_level_str).strip(" ")
            if not my_level:
                my_level = 'User'
            if ratio is None or ratio == 'null':
                continue
            if type(ratio) == str:
                ratio = ratio.strip('\n').strip()
            if float(ratio) < 0:
                ratio = 'inf'
            if not value.get(
                    'id') or key == 'latest' or not downloaded or not uploaded or not seeding_size or not my_bonus:
                continue
            create_time = dateutil.parser.parse(key).date()
            count_status = SiteStatus.objects.filter(site=my_site,
                                                     created_at__date=create_time).count()
            if count_status >= 1:
                continue
            res_status = SiteStatus.objects.update_or_create(
                site=my_site,
                created_at__date=create_time,
                defaults={
                    'uploaded': uploaded,
                    'downloaded': downloaded,
                    'ratio': float(ratio),
                    'my_bonus': my_bonus,
                    'my_level': my_level,
                    'seed_volume': seeding_size,
                    'seed': seed if seed else 0,
                })
            res_status[0].created_at = create_time
            res_status[0].save()
            logger.info(f'数据导入结果: 日期: {create_time}，True为新建，false为更新')
            logger.info(res_status)
        except Exception as e:
            msg = '{}{} 数据导入出错，错误原因：{}'.format(site.name, key, traceback.format_exc(limit=3))
            logger.error(msg)
            continue
    return CommonResponse.success(
        # status=StatusCodeEnum.NO_PASSKEY_WARNING,
        msg=site.name + (' 信息导入成功！' if result[1] else ' 信息更新成功！ ') + passkey_msg
    )


def parse_school_location(text: list):
    logger.info('解析学校访问链接：{}'.format(text))
    list1 = [x.strip().strip('"') for x in text[0].split('+')]
    list2 = ''.join(list1).split('=', 1)[1]
    return list2.strip(';').strip('"')


def parse_message_num(messages: str):
    """
    解析网站消息条数
    :param messages:
    :return:
    """
    list1 = messages.split('(')
    if len(list1) > 1:
        count = re.sub(u"([^(\u0030-\u0039])", "", list1[1])
    elif len(list1) == 1:
        count = messages
    else:
        count = 0
    return int(count)


def get_git_log(branch, n=20):
    repo = git.Repo(path='.')
    # 拉取仓库更新记录元数据
    repo.remote().fetch()
    # commits更新记录
    logger.info('当前分支{}'.format(branch))
    return [{
        'date': log.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
        'data': log.message,
        'hexsha': log.hexsha[:16],
    } for log in list(repo.iteipr_commits(branch, max_count=n))]


def generate_config_file():
    file_path = os.path.join(BASE_DIR, 'db/ptools.toml')
    try:
        if not os.path.exists(file_path):
            with open(file_path, 'w') as toml_f:
                toml_f.write('')
                toml.dump({}, toml_f)
                logger.info(f'配置文件生成成功！')
                return CommonResponse.success(
                    msg='配置文件生成成功！',
                )
        return CommonResponse.success(msg='配置文件文件已存在！', )
    except Exception as e:
        return CommonResponse.error(msg=f'初始化失败！{e}', )


def exec_command(commands):
    """执行命令行命令"""
    result = []
    for key, command in commands.items():
        p = subprocess.run(command, shell=True)
        logger.info('{} 命令执行结果：\n{}'.format(key, p))
        result.append({
            'command': key,
            'res': p.returncode
        })
    return result


def send_text(message: str, title: str = '', url: str = None):
    """通知分流"""
    notifies = Notify.objects.filter(enable=True).all()
    res = '你还没有配置通知参数哦！'
    if len(notifies) <= 0:
        return res
    try:
        for notify in notifies:
            if notify.name == PushConfig.wechat_work_push:
                """企业微信通知"""
                notify_push = WechatPush(
                    corp_id=notify.corpid,
                    secret=notify.corpsecret,
                    agent_id=notify.agentid, )
                res = notify_push.send_text(
                    text=message,
                    to_uid=notify.touser if notify.touser else '@all'
                )
                msg = '企业微信通知：{}'.format(res)
                logger.info(msg)

            if notify.name == PushConfig.wxpusher_push:
                """WxPusher通知"""
                res = WxPusher.send_message(
                    content=message,
                    url=url,
                    uids=notify.touser.split(','),
                    token=notify.corpsecret,
                    content_type=3,  # 1：文本，2：html，3：markdown
                )
                msg = 'WxPusher通知{}'.format(res)
                logger.info(msg)

            if notify.name == PushConfig.pushdeer_push:
                pushdeer = PushDeer(
                    server=notify.custom_server,
                    pushkey=notify.corpsecret)
                # res = pushdeer.send_text(text, desp="optional description")
                res = pushdeer.send_markdown(text=message,
                                             desp=title)
                msg = 'pushdeer通知{}'.format(res)
                logger.info(msg)

            if notify.name == PushConfig.bark_push:
                url = f'{notify.custom_server}{notify.corpsecret}/{title}/{message}'
                res = requests.get(url=url)
                msg = 'bark通知{}'.format(res)
                logger.info(msg)

            if notify.name == PushConfig.iyuu_push:
                url = notify.custom_server + '{}.send'.format(notify.corpsecret)
                # text = '# '
                res = requests.post(
                    url=url,
                    data={
                        'text': title,
                        'desp': message
                    })
                logger.info('爱语飞飞通知：{}'.format(res))
    except Exception as e:
        logger.info('通知发送失败，{} {}'.format(res, traceback.format_exc(limit=3)))


def today_data():
    """获取当日相较于前一日上传下载数据增长量"""
    today_site_status_list = SiteStatus.objects.filter(created_at__date=datetime.today())
    # yesterday_site_status_list = SiteStatus.objects.filter(
    #     created_at__day=datetime.today() - timedelta(days=1))
    increase_list = []
    total_upload = 0
    total_download = 0
    for site_state in today_site_status_list:
        my_site = site_state.site
        yesterday_site_status_list = SiteStatus.objects.filter(site=my_site)
        if len(yesterday_site_status_list) >= 2:
            yesterday_site_status = SiteStatus.objects.filter(site=my_site).order_by('-created_at')[1]
            uploaded_increase = site_state.uploaded - yesterday_site_status.uploaded
            downloaded_increase = site_state.downloaded - yesterday_site_status.downloaded
        else:
            uploaded_increase = site_state.uploaded
            downloaded_increase = site_state.downloaded
        if uploaded_increase + downloaded_increase <= 0:
            continue
        total_upload += uploaded_increase
        total_download += downloaded_increase
        increase_list.append(f'\n\n- 站点：{my_site.site.name}'
                             f'\n\t\t上传：{FileSizeConvert.parse_2_file_size(uploaded_increase)}'
                             f'\n\t\t下载：{FileSizeConvert.parse_2_file_size(downloaded_increase)}')
    # incremental = {
    #     '总上传': FileSizeConvert.parse_2_file_size(total_upload),
    #     '总下载': FileSizeConvert.parse_2_file_size(total_download),
    #     '说明': '数据均相较于本站今日之前最近的一条数据，可能并非昨日',
    #     '数据列表': increase_list,
    # }
    incremental = f'#### 总上传：{FileSizeConvert.parse_2_file_size(total_upload)}\n' \
                  f'#### 总下载：{FileSizeConvert.parse_2_file_size(total_download)}\n' \
                  f'> 说明: 数据均相较于本站今日之前最近的一条数据，可能并非昨日\n' \
                  f'#### 数据列表：{"".join(increase_list)}'
    logger.info(incremental)
    # todo
    # self.send_text(title='通知：今日数据', message=incremental)
