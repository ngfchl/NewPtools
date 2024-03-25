import hashlib
import json
import logging
import os
import platform
import random
import re
import subprocess
import time
import traceback
from datetime import timedelta, datetime
from typing import List, Union

import aip
import cloudscraper
import dateutil.parser
import demjson3
import feedparser
import git
import jwt
import qbittorrentapi
import requests
import telebot
import toml as toml
import transmission_rpc
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from lxml import etree
from pypushdeer import PushDeer
from telebot import apihelper

import my_site
from auxiliary.base import DownloaderCategory
from auxiliary.settings import BASE_DIR
from configuration.models import PushConfig
from download.models import Downloader
from my_site.models import SiteStatus, TorrentInfo, MySite
from toolbox.schema import CommonResponse, DotDict
from website.models import WebSite
from . import pushplus
from .cookie_cloud import CookieCloudHelper
from .wechat_push import WechatPush
from .wxpusher import WxPusher

# Create your views here.
logger = logging.getLogger('ptools')


def parse_toml(cmd) -> dict:
    """从配置文件解析获取相关项目"""
    try:
        data = toml.load('db/ptools.toml')
        return data.get(cmd, {})
    except Exception as e:
        return dict()


def check_token(token) -> bool:
    try:
        own_token = parse_toml('token').get('token')
        logger.info(f'{own_token}=={token}')
        return own_token == token
    except Exception as e:
        logger.error(e)
        return False


def cookie2dict(source_str: str) -> dict:
    """
    cookies字符串转为字典格式,传入参数必须为cookies字符串
    """
    if not source_str:
        return {}
    dist_dict = {}
    list_mid = source_str.strip().split(';')
    for i in list_mid:
        # 以第一个选中的字符分割1次，
        if len(i) <= 0:
            continue
        list2 = i.split('=', 1)
        dist_dict[list2[0].strip()] = list2[1].strip()
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
    ocr = parse_toml("ocr")
    # ocr = BaiduOCR.objects.filter(enable=True).first()
    if not ocr:
        logger.error('未设置百度OCR文本识别API，无法使用本功能！')
        return CommonResponse.error(msg='未设置百度OCR文本识别API，无法使用本功能！')
    try:
        ocr = DotDict(ocr)
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


def verify_token():
    token = os.getenv("TOKEN", None)
    if not token:
        return '您的软件未经授权，如果您喜欢本软件，欢迎付费购买授权或申请临时授权。'
    if os.path.exists(f"db/encrypted_key.bin"):
        res = subprocess.run([f"encrypt_tool/{platform.uname().machine}/main.bin"], stdout=subprocess.PIPE)
        res_json = json.loads(res.stdout)
        if res_json['code'] == 0:
            return res_json['msg']
        else:
            try:
                result = subprocess.run(['supervisorctl', 'stop', 'celery-beat'], check=True, text=True,
                                        capture_output=True)
                logger.debug(f'Successfully executed command: {result.stdout}')
            except Exception as e:
                logger.debug(f'Failed executed command')

            return '您的软件未经授权，如果您喜欢本软件，欢迎付费购买授权或申请临时授权。'
    res = requests.get('http://repeat.ptools.fun/api/user/verify', params={
        "token": token,
        "email": os.getenv("DJANGO_SUPERUSER_EMAIL", None)
    })
    if res.status_code == 200 and res.json().get('code') == 0:
        return res.json().get('msg')
    else:
        msg = f'您的软件未授权，或连接授权服务器失败！{res.json().get("msg")}'
        logger.error(msg)
        subprocess.run(['supervisorctl', 'stop', 'celery-beat'], check=True, text=True, capture_output=True)
        return msg


def send_text(message: str, title: str = '', url: str = None):
    """通知分流"""
    notifies = parse_toml("notify")
    if len(notifies) <= 0:
        msg = '你还没有配置通知参数哦！'
        logger.warning(msg)
        return msg
    try:
        message = f'> {verify_token()}  \n\n{message}'
        pass
    except Exception as e:
        msg = f'授权验证失败！'
        logger.error(msg)
        logger.error(traceback.format_exc(5))
        return msg
    for key, notify in notifies.items():
        try:
            if key == PushConfig.wechat_work_push:
                """企业微信通知"""
                server = notify.get('server', 'https://qyapi.weixin.qq.com/')
                if not server.endswith('/'):
                    server = server + '/'
                notify_push = WechatPush(
                    corp_id=notify.get('corp_id'),
                    secret=notify.get('corpsecret'),
                    agent_id=notify.get('agent_id'),
                    server=server,
                )
                max_length = 2000  # 最大消息长度限制
                if len(message) <= max_length:
                    res = notify_push.send_text(
                        text=message,
                        to_uid=notify.get('to_uid', '@all')
                    )
                else:
                    res = ''
                    while message:
                        chunk = message[:max_length]  # 从消息中截取最大长度的部分
                        res = notify_push.send_text(
                            text=chunk,
                            to_uid=notify.get('to_uid', '@all')
                        )
                        message = message[max_length:]  # 剩余部分作为新的消息进行下一轮发送
                        logger.info(res)
                msg = f'企业微信通知：{res}'
                logger.info(msg)

            if key == PushConfig.wxpusher_push:
                """WxPusher通知"""
                res = WxPusher.send_message(
                    summary=title,
                    content=message,
                    url=url,
                    uids=notify.get('uids').split(','),
                    token=notify.get('token'),
                    content_type=3,  # 1：文本，2：html，3：markdown
                )
                msg = 'WxPusher通知{}'.format(res)
                logger.info(msg)

            if key == PushConfig.pushdeer_push:
                pushdeer = PushDeer(
                    server=notify.get('custom_server', 'https://api2.pushdeer.com'),
                    pushkey=notify.get('pushkey')
                )
                # res = pushdeer.send_text(text, desp="optional description")
                res = pushdeer.send_markdown(text=message,
                                             desp=title)
                msg = 'pushdeer通知{}'.format(res)
                logger.info(msg)

            if key == PushConfig.bark_push:
                res = requests.post(
                    url=f'{notify.get("custom_server", "https://api.day.app/")}push',
                    data={
                        'title': title,
                        'body': message,
                        'device_key': notify.get("device_key"),
                        # 'url': 'http://img.ptools.fun/pay.png',
                        'icon': 'https://gitee.com/ngfchl/ptools/raw/master/static/logo4.png'
                    },
                )
                msg = 'bark通知 {}'.format(res.json())
                logger.info(msg)

            if key == PushConfig.iyuu_push:
                url = notify.get("custom_server", 'http://iyuu.cn/') + '{}.send'.format(notify.get("token"))
                # text = '# '
                res = requests.post(
                    url=url,
                    data={
                        'text': title,
                        'desp': message
                    })
                msg = f'爱语飞飞通知：{res}'
                logger.info(msg)

            if key == PushConfig.telegram_push:
                """Telegram通知"""
                telegram_token = notify.get('telegram_token')
                telegram_chat_id = notify.get('telegram_chat_id')
                bot = telebot.TeleBot(telegram_token)
                proxy = notify.get('proxy')
                if proxy:
                    apihelper.proxy = proxy
                max_length = 4096  # 最大消息长度限制
                parse_mode = notify.get('parse_mode') if notify.get('parse_mode') else "HTML"
                if len(message) <= max_length:
                    bot.send_message(telegram_chat_id, message, parse_mode=parse_mode)  # 如果消息长度不超过最大限制，直接发送消息
                else:
                    while message:
                        chunk = message[:max_length]  # 从消息中截取最大长度的部分
                        bot.send_message(telegram_chat_id, chunk, parse_mode=parse_mode)  # 发送消息部分
                        message = message[max_length:]  # 剩余部分作为新的消息进行下一轮发送

                msg = 'Telegram通知成功'
                logger.info(msg)
            if key == PushConfig.pushplus:
                token = notify.get('token')
                template = notify.get('template') if notify.get('template') else "markdown"
                res = pushplus.send_text(token=token, title=title, content=message, template=template)
                logger.info(res)
        except Exception as e:
            msg = f'通知发送失败，{traceback.format_exc(limit=5)}'
            logger.error(msg)


def get_git_log(branch='master', n=5):
    repo = git.Repo(path='.')
    # 拉取仓库更新记录元数据
    repo.remote().set_url('git@gitee.com:ngfchl/auxiliary.git')
    repo.git.config('core.sshCommand', f'ssh -i /root/.ssh/id_rsa')
    repo.remote().fetch()
    # commits更新记录
    logger.info('当前分支{}'.format(branch))
    return [{
        'date': log.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
        'data': log.message,
        'hex': log.hexsha[:16],
    } for log in list(repo.iter_commits(branch, max_count=n))]


def today_data():
    """获取当日相较于前一日上传下载数据增长量"""
    today_site_status_list = SiteStatus.objects.filter(created_at__date=datetime.today())
    increase_info_list = []
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
        increase_info_list.append({
            'name': my_site.nickname,
            'uploaded': uploaded_increase,
            'downloaded': downloaded_increase
        })
    increase_info_list.sort(key=lambda x: x.get('uploaded'), reverse=True)
    return total_upload, total_download, increase_info_list


def get_token(payload, timeout):
    salt = settings.SECRET_KEY
    payload["exp"] = datetime.utcnow() + timedelta(minutes=timeout)  # 设置到期时间
    # token = jwt.encode(payload=payload, key=salt, headers=headers).decode("utf-8")
    token = jwt.encode(payload=payload, key=salt, algorithm="HS256")
    return token


def parse_ptpp_cookies(data_list):
    # 解析前端传来的数据
    datas = json.loads(data_list.cookies)
    info_list = json.loads(data_list.info)
    # userdata_list = json.loads(data_list.userdata)
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
                # 'userdatas': userdata_list.get(host)
            })
        logger.info('站点记录共{}条'.format(len(cookies)))
        # logger.info(cookies)
        return cookies
    except Exception as e:
        # raise
        # 打印异常详细信息
        logger.error(traceback.format_exc(limit=3))
        send_text(title='PTPP站点导入通知', message='Cookies解析失败，请确认导入了正确的cookies备份文件！')
        return 'Cookies解析失败，请确认导入了正确的cookies备份文件！'


def parse_rss(rss_url: str):
    """
    分析RSS订阅信息
    :param rss_url:
    :return: 解析好的种子列表
    """
    feed = feedparser.parse(rss_url)
    torrents = []
    for article in feed.entries:
        # logger.info(article.published).get('enclosure').get('url'))
        # logger.info(time.strftime('%Y-%m-%d %H:%M:%S', article.published_parsed))
        link = article.links[-1]
        torrents.append({
            'title': article.title[:255],
            'tid': (article.link.split('=')[-1]),
            'size': link.get('length'),
            'magnet_url': link.get('href'),
            'published': datetime.fromtimestamp(time.mktime(article.published_parsed)),
        })
    return torrents


def get_downloader_instance(downloader_id):
    """根据id获取下载实例"""
    try:
        downloader = Downloader.objects.filter(id=downloader_id).first()
        if not downloader:
            msg = f"请确认当前所选下载器是否存在！"
            logger.error(msg)
            return None, msg, None
        if downloader.category == DownloaderCategory.qBittorrent:
            client = qbittorrentapi.Client(
                host=downloader.host,
                port=downloader.port,
                username=downloader.username,
                password=downloader.password,
                SIMPLE_RESPONSES=True,
                REQUESTS_ARGS={
                    'timeout': (5, 60)
                }
            )
            client.auth_log_in()
        else:
            client = transmission_rpc.Client(
                host=downloader.host, port=downloader.port,
                protocol=downloader.http,
                username=downloader.username,
                password=downloader.password,
                timeout=60,
            )
        return client, downloader.category, downloader.name
    except Exception as e:
        logger.error(traceback.format_exc(3))
        msg = f'下载器连接失败：{e}'
        logger.exception(msg)
        return None, msg, None


def get_downloader_speed(downloader: Downloader):
    """获取单个下载器速度信息"""
    try:
        client, _, _ = get_downloader_instance(downloader.id)
        if not client:
            return {
                'category': downloader.category,
                'name': f'{downloader.name} 链接失败',
                'free_space_on_disk': 0,
                'connection_status': False,
                'dl_info_data': 0,
                'dl_info_speed': 0,
                'up_info_data': 0,
                'up_info_speed': 0,
            }
        if downloader.category == DownloaderCategory.qBittorrent:
            # x = {'connection_status': 'connected', 'dht_nodes': 0, 'dl_info_data': 2577571007646,
            #      'dl_info_speed': 3447895, 'dl_rate_limit': 41943040, 'up_info_data': 307134686158,
            #      'up_info_speed': 4208516, 'up_rate_limit': 0, 'category': 'Qb', 'name': 'home-qb'}
            info = client.sync_maindata().get('server_state')
            info.update({
                'category': downloader.category,
                'name': downloader.name,
                'connection_status': True if info.get('connection_status') == 'connected' else False,
            })
            return info
        elif downloader.category == DownloaderCategory.Transmission:
            base_info = client.session_stats().fields
            return {
                'connection_status': True,
                'free_space_on_disk': client.raw_session.get('download-dir-free-space'),
                # 'dht_nodes': 0,
                'dl_info_data': base_info.get('cumulative-stats').get('downloadedBytes'),
                'dl_info_speed': base_info.get('downloadSpeed'),
                # 'dl_rate_limit': 41943040,
                'up_info_data': base_info.get('cumulative-stats').get('uploadedBytes'),
                'up_info_speed': base_info.get('uploadSpeed'),
                # 'up_rate_limit': 0,
                'category': downloader.category,
                'name': downloader.name
            }
        else:
            return {
                'category': downloader.category,
                'name': downloader.name,
                'connection_status': False,
                'free_space_on_disk': 0,
                'dl_info_data': 0,
                'dl_info_speed': 0,
                'up_info_data': 0,
                'up_info_speed': 0,
            }
    except Exception as e:
        return {
            'category': downloader.category,
            'name': downloader.name,
            'free_space_on_disk': 0,
            'connection_status': False,
            'dl_info_data': 0,
            'dl_info_speed': 0,
            'up_info_data': 0,
            'up_info_speed': 0,
        }


def push_torrents_to_downloader(
        client,
        downloader_category: DownloaderCategory.choices,
        urls: Union[List[str], str],
        category: str = None,
        save_path: str = None,
        cookie: str = '',
        upload_limit: int = 0,
        download_limit: int = 150,
        is_paused: bool = None,
        is_skip_checking: bool = None,
        use_auto_torrent_management: bool = None,
):
    """将辅种数据推送至下载器"""
    # 暂停模式推送至下载器（包含参数，下载链接，Cookie，分类或者下载路径）
    # 开始校验
    # 验证校验结果，不为百分百的，暂停任务
    if downloader_category == DownloaderCategory.qBittorrent:
        res = client.torrents.add(
            urls=urls.split('|'),
            category=category,
            save_path=save_path,
            is_skip_checking=is_skip_checking,
            is_paused=is_paused,
            upload_limit=upload_limit * 1024 * 1024,
            download_limit=download_limit * 1024 * 1024,
            use_auto_torrent_management=use_auto_torrent_management,
            cookie=cookie,
        )
        if res == 'Ok.':
            return CommonResponse.success(msg=f'种子已添加，请检查下载器！{res}')
        return CommonResponse.error(msg=f'种子添加失败！{res}')
    if downloader_category == DownloaderCategory.Transmission:
        msg_list = []
        for url in urls.split('|'):
            try:
                res = client.add_torrent(
                    torrent=url,
                    download_dir=category,
                    paused=is_paused,
                    cookies=cookie
                )
                if res.hashString and len(res.hashString) >= 0:
                    msg = f'种子已添加，请检查下载器！{res.name}'
                    logger.info(msg)
                else:
                    msg = f'种子添加失败：{url}'
                    logger.warning(msg)
            except Exception as e:
                msg = f'种子添加失败：{url}  {e}'
                logger.error(msg)
            msg_list.append(msg)
        return CommonResponse.success(msg='，'.join(msg_list))


def package_files(
        client, hash_string, package_size: int = 10,
        delete_one_file: bool = False,
        package_percent: float = 0.1
):
    """
    种子文件拆包，只下载部分，默认大于10G的种子才进行拆包
    :param package_percent: 拆包到多小,原大小的十分之一
    :param delete_one_file: 只有一个文件且达到拆包标准时是否删除
    :param package_size: 拆包大小，单位GB
    :param client: 下载器
    :param hash_string: HASH
    :return:
    """
    # 种子属性
    try:
        prop = client.torrents_properties(torrent_hash=hash_string)
        # 种子总大小
        total_size = prop.get('total_size')
        # 如果文件总大小大于package_size，则进行拆包，数字自定义
        if total_size <= package_size * 1024 * 1024 * 1024:
            client.torrents_resume(torrent_hashes=hash_string)
        if total_size > package_size * 1024 * 1024 * 1024:
            # 获取种子文件列表信息
            files = client.torrents_files(torrent_hash=hash_string)
            # 获取所有文件index
            total_ids = [file.get('index') for file in files if file.get('priority') == 1]
            # 从大到小排列种子
            files = sorted(files, key=lambda x: x.get('size'), reverse=True)
            # 只有一个文件且大于15G的删掉
            if len(files) == 1 and total_size > 15 * 1024 * 1024 * 1024 and delete_one_file:
                client.torrents_delete(torrent_hash=hash_string)
                return
            # 两个文件的
            if len(files) == 2:
                # 如果第二个文件大小小于500M或者大于15G的删掉
                # if files[1].size < 500 * 1024 * 1024 or files[1].size > 15 * 1024 * 1024 * 1024:
                #     client.torrents_delete(torrent_hash=hash_string)
                # 设置只下载第二个文件
                client.torrents_file_priority(
                    torrent_hash=hash_string,
                    file_ids=0,
                    priority=0
                )
                return
            # 超过三个文件的，先排除最大的和最小的
            files = files[1:-1]
            # 然后打乱顺序
            random.shuffle(files)
            ids = []
            size = 0
            # 循环获取文件index，当总大小超过总大小的十分之一时结束
            for file in files:
                size += file.get('size')
                ids.append(file.get('index'))
                if size > total_size * package_percent:
                    break
            # 如果最后获取的文件大小小于800M
            # if size < 500 * 1024 * 1024:
            #     client.torrents_delete(torrent_hash=hash_string)
            #     return
            # 计算需要取消下载的文件index列表，将总列表和需要下载的列表转为集合后相减
            delete_ids = list(set(total_ids) - set(ids))
            if len(delete_ids) > 0:
                logger.info(f'需要取消下载的文件ID：{delete_ids}')
                client.torrents_file_priority(
                    torrent_hash=hash_string,
                    file_ids=delete_ids,
                    priority=0
                )
                client.torrents_resume(torrent_hash=hash_string)
                msg = f'种子 {hash_string} 拆包完成'
                logger.info(msg)
            else:
                msg = f'种子 {hash_string} 无需拆包，跳过'
                logger.info(msg)
            return CommonResponse.success(msg=msg)
    except Exception as e:
        msg = f'种子 {hash_string} 拆包失败！'
        logger.error(f'{traceback.format_exc(3)} \n {msg}')
        return CommonResponse.error(msg=msg)


def filter_torrent_by_rules(mysite: MySite, torrents: List[TorrentInfo]):
    """
    使用站点选中规则筛选种子
    :param mysite: 我的站点
    :param torrents: 种子列表
    :return: 筛选过后的种子列表
    """
    rules = demjson3.decode(mysite.remove_torrent_rules).get('push')
    logger.info(f"当前站点：{mysite.nickname}, 选种规则：{rules}")

    # 收集不符合规则的种子
    excluded_torrents = []

    for torrent in torrents:
        try:
            logger.info(f'选种开始，当前种子：{torrent.title}')
            # 包含关键字命中
            includes = rules.get('include')
            if includes and len(includes) > 0:
                logger.debug(f'当前包含关键字检查：{includes}')
                if not any(rule in torrent.title for rule in includes):
                    logger.info(f'关键字未命中，继续')
                    excluded_torrents.append(torrent)
                    # 跳过该种子的处理，继续下一个种子的判断
                else:
                    logger.info(f'关键字命中！')
                    continue

            # 排除关键字命中
            excludes = rules.get('exclude')
            if excludes and len(excludes) > 0:
                logger.debug(f'当前排除关键字检查：{includes}')

                if all(rule not in torrent.title for rule in excludes):
                    logger.info(f'排除关键字未命中，跳过')
                    excluded_torrents.append(torrent)
                    torrent.state = 5
                    torrent.save()
                    # 跳过该种子的处理，继续下一个种子的判断
                    continue

            # 种子大小命中
            size = rules.get('size')
            if size:
                min_size = size.get('min') * 1024 * 1024 * 1024
                max_size = size.get('max') * 1024 * 1024 * 1024
                logger.info(
                    f'当前种子大小检测：设定最小：{size.get("min")} GB,'
                    f'设定最大：{size.get("max")} GB,'
                    f'当前：{int(torrent.size) / 1024 / 1024 / 1024} GB'
                )
                if not int(min_size) < int(torrent.size) < int(max_size):
                    logger.warning('🈲 触发种子大小规则，排除')
                    excluded_torrents.append(torrent)
                    torrent.state = 5
                    torrent.save()
                    continue
            # 剩余免费时间命中
            sale_expire = rules.get('sale_expire')
            if sale_expire:
                logger.debug(
                    f'设定剩余免费时间：{sale_expire}，当前种子免费到期时间：{torrent.sale_status}: {torrent.sale_expire}')
                exp = torrent.sale_expire
                if not exp:
                    logger.warning(f'🈲 当前种子优惠到期时间：{exp}, 跳过')
                else:
                    if isinstance(exp, str):
                        exp = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")
                    # 如果种子有到期时间，且到期时间小于设定值，排除
                    if isinstance(exp, datetime) and (exp - datetime.now()).total_seconds() < sale_expire:
                        logger.warning('🈲 触发剩余免费时间规则，排除')
                        excluded_torrents.append(torrent)
                        # 跳过该种子的处理，继续下一个种子的判断
                        torrent.state = 5
                        torrent.save()
                        continue
            # 发种时间命中
            published = rules.get('published')
            if published:
                logger.info(f'发种时间检查：{published}')
                torrent_published = datetime.strptime(torrent.published, "%Y-%m-%d %H:%M:%S") if isinstance(
                    torrent.published, str) else torrent.published
                logger.info(f'当前种子发种时间检查：{torrent_published}')
                if (datetime.now() - torrent_published).total_seconds() > published:
                    logger.warning('🈲 触发发种时间规则，排除')
                    excluded_torrents.append(torrent)
                    # 跳过该种子的处理，继续下一个种子的判断
                    torrent.state = 5
                    torrent.save()
                    continue
            # 做种人数命中
            seeders = rules.get('seeders')
            if seeders:
                logger.debug(f'设定做种人数：{seeders}，当前种子做种人数：{torrent.seeders}')
                if torrent.seeders > seeders:
                    logger.warning('🈲 触发当前做种人数规则，排除')
                    excluded_torrents.append(torrent)
                    # 跳过该种子的处理，继续下一个种子的判断
                    continue
            # 下载人数命中
            leechers = rules.get('leechers')
            if leechers:
                logger.debug(f'设定下载人数：{leechers}，当前种子下载人数：{torrent.leechers}')
                if torrent.leechers < leechers:
                    logger.warning('🈲 触发当前下载人数规则，排除')
                    excluded_torrents.append(torrent)
                    # 跳过该种子的处理，继续下一个种子的判断
                    continue

        except Exception:
            logger.error(traceback.format_exc(3))
            continue

    # 一次性保存所有不符合规则的种子
    # for excluded_torrent in excluded_torrents:
    #     excluded_torrent.state = 5
    #     excluded_torrent.save()

    # 返回符合规则的种子列表
    return list(set(torrents) - set(excluded_torrents))


def sha1_hash(string: str) -> str:
    return hashlib.sha1(string.encode()).hexdigest()


def remove_torrent_by_site_rules(mysite: MySite):
    """
    站点删种
    :param mysite:
    :return msg
    """
    rules = demjson3.decode(mysite.remove_torrent_rules).get('remove')
    logger.info(f"当前站点：{mysite}, 删种规则：{rules}")
    logger.info(f"当前下载器：{mysite.downloader_id}")
    client, _, _ = get_downloader_instance(mysite.downloader.id)
    if not client:
        return CommonResponse.error(msg=f'{mysite.nickname} - 下载器 {mysite.downloader.name} 链接失败!')
    website = WebSite.objects.get(id=mysite.site)
    count = 0
    hashes = []
    expire_hashes = []
    torrents = [torrent for torrent in client.torrents_info() if torrent.get('category').find(website.nickname) >= 0]
    logger.info(f'当前下载器共有站点 {website.name} 种子数量：{len(torrents)}')
    # hash_torrents = {item.get('hash'): item for item in torrents}
    logger.info(f'开始循环处理种子')
    torrent_infos = mysite.torrentinfo_set.all()
    for torrent in torrents:
        category = torrent.get('category')
        hash_string = torrent.get('hash')
        if category.find('-'):
            try:
                _, tid = category.split('-')
                logger.info(f'当前种子ID：{tid}')
                torrent_info = torrent_infos.get(tid=tid)
                torrent_info.hash_string = hash_string
            except my_site.models.TorrentInfo.DoesNotExist:
                logger.info(f'未在数据库中找到当前种子')
                continue
            except Exception as e:
                logger.error(f'查找当前种子失败：{e}')
                logger.error(traceback.format_exc(5))
                continue
        else:
            logger.warning(f'非本工具刷流种子，跳过！')
            continue

        try:
            # 通过qbittorrentapi客户端获取种子的块哈希列表和文件列表，并转换为字符串
            logger.info(f'开始完善种子信息')
            try:
                if not torrent_info.pieces_qb:
                    # 获取种子块HASH列表，并生成种子块HASH列表字符串的sha1值，保存
                    pieces_hash_list = client.torrents_piece_hashes(torrent_hash=hash_string)
                    pieces_hash_string = ''.join(str(pieces_hash) for pieces_hash in pieces_hash_list)
                    torrent_info.pieces_qb = sha1_hash(pieces_hash_string)
                if not torrent_info.filelist:
                    # 获取文件列表，并生成文件列表字符串的sha1值，保存
                    file_list = client.torrents_files(torrent_hash=hash_string)
                    file_list_hash_string = ''.join(str(item) for item in file_list)
                    torrent_info.filelist = sha1_hash(file_list_hash_string)
                    torrent_info.files_count = len(file_list)
                torrent_info.save()
            except qbittorrentapi.exceptions.NotFound404Error:
                msg = f'{torrent_info.title}: 完善hash失败!--下载器已删种！'
                torrent_info.state = 3
                torrent_info.save()
                logger.error(msg)
                continue
            except Exception as e:
                msg = f'{torrent_info.title}: 完善种子失败！'
                logger.error(traceback.format_exc(3))
                logger.error(msg)
            # 保存种子属性
            torrent_info.save()

            # 删种
            logger.info(f'{torrent_info.title} - 开始匹配删种规则: {hash_string}')
            prop = client.torrents_properties(torrent_hash=hash_string)

            # 磁盘空间检查
            keep_free_space = rules.get('keep_free_space')
            if keep_free_space and keep_free_space > 0:
                logger.debug(f'设定不删种空间大小：{keep_free_space} GB')
                free_space = client.sync_maindata().get('server_state').get('free_space_on_disk')
                logger.debug(f'当前下载器剩余空间大小：{free_space / 1024 / 1024 / 1024} GB ')
                if free_space > keep_free_space * 1024 * 1024 * 1024:
                    logger.info(f'下载器剩余空间充足，不执行删种操作！')
                    continue

            # 排除关键字命中，
            delete_flag = False
            logger.info(f'排除关键字: {hash_string}')
            if rules.get('exclude'):
                for rule in rules.get('exclude'):
                    if torrent.get('title').find(rule) > 0:
                        delete_flag = True
                        logger.info(f"🚫{mysite.nickname} {torrent.get('tid')} 排除关键字命中：{delete_flag}")
                        break
            if delete_flag:
                # 遇到要排除的关键字的种子，直接跳过，不再继续执行删种
                continue

            # 免费到期检测
            logger.info(f'免费到期检测: {hash_string}')
            if not torrent_info.sale_expire:
                logger.info(f'{torrent_info.title} 免费过期时间：{torrent_info.sale_expire}')
            else:
                torrent_sale_expire = torrent_info.sale_expire.timestamp()
                sale_expire = rules.get('sale_expire', {"expire": 300, "delete_on_completed": True})
                expire_time = sale_expire.get('expire', 300)
                delete_flag = sale_expire.get('delete_on_completed')
                if torrent_sale_expire - time.time() <= expire_time and (prop.get('completion_date') < 0 or (
                        prop.get('completion_date') > 0 and delete_flag)):
                    expire_hashes.append(hash_string)
                    logger.debug(f'🚫{torrent_info.title} 免费即将到期 命中')
                    continue
            # 指定时间段内平均速度
            logger.info(f'指定时间段内平均速度: {hash_string}')
            upload_speed_avg = rules.get("upload_speed_avg")
            logger.debug(f'指定时间段内平均速度检测: {upload_speed_avg}')
            if upload_speed_avg:
                # 从缓存获取指定时间段平均速度检测数据
                upload_speed_avg_list = cache.get(f'{hash_string}__update_uploaded', [])
                # 如果数据为空，则添加初始化数据
                if len(upload_speed_avg_list) <= 0:
                    cache.set(f'{hash_string}_update_uploaded', [{
                        "check_time": prop.get("addition_date"),
                        "uploaded": 0
                    }])
                # 获取当前数据并添加到检测数据中
                now = time.time()
                now_uploaded = prop.get("total_uploaded")
                upload_speed_avg_list.append({
                    "check_time": now,
                    "uploaded": now_uploaded
                })
                # 获取列表中最早的一条数据
                earliest_uploaded_info = upload_speed_avg_list[0]
                # 计算当前数据与最早一条数据的时间差
                time_delta = now - earliest_uploaded_info.get("check_time")
                if time_delta < upload_speed_avg.get("time"):
                    # 若时间差未达到检测时间，跳过
                    logger.info(f'当前种子运行时间未达到检测时间：{time_delta} < {upload_speed_avg.get("time")}')
                else:
                    # 达到检测标准的，获取数据的上传量信息，计算这时间段内的平均速度
                    earliest_uploaded = earliest_uploaded_info.get("uploaded")
                    uploaded_eta = now_uploaded - earliest_uploaded
                    uploaded_avg = uploaded_eta / time_delta
                    logger.debug(f'{torrent_info.title} 上传速度 {uploaded_avg / 1024} ')
                    if uploaded_avg < upload_speed_avg.get("upload_speed") * 1024:
                        # 如果平均速度不达标，删种
                        cache.remove(f'{hash_string}_update_uploaded')
                        logger.debug(f'🚫 {upload_speed_avg.get("upload_speed")} 不达标删种 命中')
                        hashes.append(hash_string)
                        continue
                    else:
                        # 达标的，删除最早的数据，并将新数据存入缓存
                        upload_speed_avg_list.pop(0)
                        cache.set(f'{hash_string}_update_uploaded', upload_speed_avg_list)
            logger.debug(f'{hash_string} -- {torrent_info.title} 上传速度不达标删种 未命中')
            logger.debug(f'站点删种检测')
            not_registered_msg = [
                'torrent not registered with this tracker',
                'err torrent deleted due to other',
                'Torrent not exists',
            ]
            trackers = client.torrents_trackers(torrent_hash=hash_string)
            tracker_checked = False
            for tracker in trackers:
                delete_msg = [msg for msg in not_registered_msg if tracker.get('msg').lower().startswith(msg)]
                if len(delete_msg) > 0:
                    hashes.append(hash_string)
                    tracker_checked = True
                    break
            if tracker_checked:
                logger.debug(f'🚫{hash_string} -- {torrent_info.title} 站点删种 命中')
                torrent_info.state = 4
                torrent_info.save()
                continue
            else:
                logger.debug(f'{hash_string} -- {torrent_info.title} 站点删种 未命中')
            # 完成人数超标删除
            logger.info(f'完成人数检测: {torrent_info.title}')
            torrent_num_complete = rules.get("num_completer")
            logger.debug(f'{hash_string} -- {torrent_info.title} 完成人数超标删除: {torrent_num_complete}')
            if torrent_num_complete:
                completers = torrent_num_complete.get("completers")
                upspeed = torrent_num_complete.get("upspeed")
                num_complete = prop.get('seeds_total')
                logger.debug(f'当前种子已完成人数：{num_complete} -- 设定人数：{completers}')
                logger.debug(f'当前种子上传速度：{torrent.get("upspeed")} -- 设定速度：{upspeed}')
                if num_complete > completers and torrent.get("upspeed") < upspeed:
                    logger.debug(
                        f'🚫{torrent_info.title} 完成人数 {num_complete} 超标,'
                        f'当前速度 {torrent.get("upspeed")} 不达标 命中'
                    )
                    hashes.append(hash_string)
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 完成人数未超标 未命中')
            # 正在下载人数 低于设定值删除
            logger.info(f'正在下载人数检测: {torrent_info.title}')
            torrent_num_incomplete = rules.get("num_incomplete")
            logger.debug(f'完成人数超标删除: {torrent_num_incomplete}')
            if torrent_num_incomplete and len(torrent_num_incomplete) > 0:
                num_incomplete = torrent.get('num_incomplete')
                logger.debug(f'{hash_string} -- {torrent_info.title} 正在下载完成人数不达标: {num_incomplete}')
                if num_incomplete < torrent_num_incomplete:
                    logger.debug(f'🚫{hash_string} -- {torrent_info.title} 正在下载人数 低于设定值 命中')
                    hashes.append(hash_string)
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 正在下载人数 高于设定值 未命中')
            # 无上传无下载超时删种
            logger.info(f'活跃度检测: {hash_string}')
            logger.debug(f'完成人数超标删除: {rules.get("timeout") and rules.get("timeout") > 0}')
            if rules.get("timeout") and rules.get("timeout") > 0:
                last_activity = torrent.get('last_activity')
                logger.debug(f'{hash_string} -- {torrent_info.title} 最后活动时间: {time.time() - last_activity}')
                if time.time() - last_activity > rules.get("timeout"):
                    logger.debug(f'🚫{hash_string} -- {torrent_info.title} 无活动超时 命中')
                    hashes.append(hash_string)
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 无活动超时 未命中')
            # 进度与平均上传速度达标检测
            progress = torrent.get('progress')
            progress_check = rules.get("progress_check")
            logger.debug(f'进度与平均上传速度达标检测: {progress_check}')
            if progress_check and len(progress_check) > 0:
                progress_checked = False
                for key, value in progress_check.items():
                    logger.debug(
                        f'{hash_string}-{torrent_info.title} 指定进度{float(key)},'
                        f'指定速度{value / 1024} MB/S,平均上传速度: {prop.get("up_speed_avg") / 1024 / 1024} MB/S'
                    )
                    if progress < float(key):
                        continue
                    elif prop.get('up_speed_avg') < value * 1024:
                        hashes.append(hash_string)
                        progress_checked = True
                        logger.debug(
                            f'🚫{hash_string}-{torrent_info.title} 指定进度与平均上传速度达标检测低于设定值 命中')
                        break
                if progress_checked:
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 指定进度与平均上传速度达标检测 高于设定值 未命中')
            # 达到指定分享率
            ratio = prop.get('share_ratio')

            if rules.get("max_ratio"):
                logger.info(f'分享率检测: {hash_string}')
                if progress < 1:
                    logger.debug(f'{hash_string} -- {torrent_info.title} 尚未下载完毕！ 未命中')
                elif ratio >= rules.get("max_ratio"):
                    hashes.append(hash_string)
                    logger.debug(f'🚫{hash_string} -- {torrent_info.title} 已达到指定分享率 命中')
                    continue
                else:
                    logger.debug(f'{hash_string} -- {torrent_info.title} 未达到指定分享率 未命中')

            # 指定时间段内分享率不达标
            ratio_check = rules.get("ratio_check")
            logger.debug(f'指定时间段内分享率不达标: {ratio_check}')
            if ratio_check and len(ratio_check) > 0:
                ratio_checked = False
                time_active = prop.get('time_elapsed')
                for key, value in ratio_check.items():
                    logger.debug(
                        f'{hash_string}-{torrent_info.title} 指定时长{float(key)},指定分享率{value}，当前分享率：{ratio}'
                    )
                    if time_active < float(key):
                        logger.debug(f'活动时间：{time_active / 60}分钟 尚未达到指定下载时长：{float(key)}')
                        continue
                    if ratio < value:
                        logger.debug(f'🚫{hash_string} -- {torrent_info.title} 指定时间段内分享率不达标 低于设定值 命中')
                        hashes.append(hash_string)
                        ratio_checked = True
                        break
                if ratio_checked:
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 指定时间段内分享率达标 未命中')
        except qbittorrentapi.exceptions.NotFound404Error:
            msg = f'{torrent_info.title}: 完善信息失败!--下载器已删种！'
            torrent_info.state = 3
            logger.error(msg)
            torrent_info.save()
        except Exception as e:
            logger.error(traceback.format_exc(3))
            msg = '完善种子或解析删种规则失败！'
            logger.error(msg)
            continue
    logger.info(
        f'🚫{mysite.nickname}-本次运行完善{count}个种子信息！删种规则命中任务:{len(hashes)}个，免费即将到期命中：{len(expire_hashes)}个')
    try:
        count = 0
        if len(hashes) + len(expire_hashes) > 0:
            client.torrents_reannounce(torrent_hashes=hashes)
            # 单次最多删种数量, 不填写默认所有被筛选的, 免费到期的不算在内
            num_delete = rules.get("num_delete", 0)
            if num_delete > 0:
                random.shuffle(hashes)
                hashes = hashes[:num_delete]
            hashes.extend(expire_hashes)
            client.torrents_delete(torrent_hashes=hashes, delete_files=True)
            # 对已删除的种子信息进行归档
            count = TorrentInfo.objects.filter(
                hash_string__in=hashes
            ).update(state=5, downloader=None)
            msg = f'{mysite.nickname}：本次运行删除种子{count}个！'
        else:
            msg = f'{mysite.nickname}：本次运行没有种子要删除！'
        logger.info(msg)
        # 启动所有种子
        client.torrents_resume(torrent_hashes='all')
        return CommonResponse.success(msg=msg, data=count)
    except Exception as e:
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=f'{mysite.nickname} - 删种出错啦！')


def torrents_filter_by_percent_completed_rule(client, num_complete_percent, downloaded_percent):
    """
    种子筛选之 下载进度筛选
    :param client: 客户端，仅支持QB
    :param num_complete_percent: 达标人数
    :param downloaded_percent: 已完成百分比
    :return:
    """
    torrents = client.torrents.info()
    hashes = []
    for torrent in torrents:
        hash_string = torrent.get('hash')
        progress = torrent.get('progress')
        if progress >= 1:
            continue
        not_registered_msg = [
            'torrent not registered with this tracker',
            'err torrent deleted due to other',
            'err torrent deleted due to repack, related torrent: /details.php?id='
        ]
        trackers = client.torrents_trackers(torrent_hash=hash_string)
        tracker_checked = False
        for tracker in [t for t in trackers if t.get('tier') == 0]:
            delete_msg = [msg for msg in not_registered_msg if msg in tracker.get('msg')]
            if len(delete_msg) > 0:
                hashes.append(hash_string)
                tracker_checked = True
                break
        if tracker_checked:
            continue
        # if torrent.get('num_complete') > 10:
        #     hashes.append(hash_string)
        #     continue

        category = torrent.get('category')
        if len(category) <= 0:
            continue
        num_complete = torrent.get('num_complete')
        uploaded = torrent.get('uploaded')
        ratio = torrent.get('ratio')
        time_active = torrent.get('time_active')
        if time_active > 1800 and ratio < 0.01:
            hashes.append(hash_string)
            continue
        if num_complete > 5:
            hashes.append(hash_string)
            continue
        # elif time_active > 600 and uploaded / time_active < 50:
        #     hashes.append(hash_string)
        peer_info = client.sync_torrent_peers(torrent_hash=hash_string)
        peers = peer_info.get('peers').values()
        num_peers = len(peers)
        if num_peers > 0:
            progress = [peer.get('progress') for peer in peers]
            high_progress = [p for p in progress if p > downloaded_percent]
            if len(high_progress) / num_peers > num_complete_percent:
                hashes.append(hash_string)
    return hashes


def get_torrents_hash_from_iyuu(hash_list: List[str]):
    try:
        hash_list.sort()
        iyuu_token = parse_toml('repeat').get('iyuu_token')
        logger.info(f'IYUU - TOKEN：{iyuu_token}')
        # 由于json解析的原因，列表元素之间有空格，需要替换掉所有空格
        hash_list_json = json.dumps(hash_list).replace(' ', '')
        hash_list_sha1 = hashlib.sha1(hash_list_json.encode(encoding='utf-8')).hexdigest()
        url = f'{os.getenv("IYUU_SERVER")}/index.php?s=App.Api.Infohash'
        data = {
            # IYUU token
            'sign': iyuu_token,
            # 当前时间戳
            'timestamp': int(time.time()),
            # 客户端版本
            'version': '2.0.1',
            # hash列表
            'hash': hash_list_json,
            # hash列表sha1
            'sha1': hash_list_sha1
        }
        res = requests.post(url=url, data=data).json()
        ret = res.get('ret')
        logger.info(f'辅种返回消息码：{ret}，返回消息：{res.get("msg")}，返回数据：{res.get("data")}')
        if ret == 200:
            site_list = WebSite.objects.all()
            iyuu_data = res.get('data')
            repeat_info = {}
            for hash_string, values in iyuu_data.items():
                try:
                    current_list = []

                    for t in values.get("torrent"):
                        info_hash = t.get('info_hash')
                        if info_hash in hash_list:
                            logger.warning(f'{info_hash} 本地已存在，跳过！')
                            continue
                        tid = t.get('torrent_id')
                        sid = t.get('sid')
                        try:
                            site = site_list.filter(iyuu=sid).first()
                            logger.info(f'当前站点：{site}')
                            if not isinstance(site, WebSite):
                                # 站点尚未支持，跳过
                                logger.warning(f"尚未支持的IYUU站点：{sid}")
                                continue
                            base_dict = {
                                "site_id": site.id,
                                "tid": tid,
                                "hash_string": info_hash,
                            }
                            current_list.append(base_dict)
                        except Exception as e:
                            logger.error(f' IYUU 数据: {info_hash} -tid: {tid} - iyuu: {sid} 解析出错了：{e}')
                            logger.error(traceback.format_exc(5))
                            continue
                    repeat_info[hash_string] = current_list
                except Exception as e:
                    logger.error(f'解析 IYUU 数据出错了：{e}')
                    logger.error(traceback.format_exc(5))
            return CommonResponse.success(data=repeat_info)
        return CommonResponse.error(msg=res.get('msg'))
    except Exception as e:
        msg = f'从IYUU获取辅种数据失败！{e}'
        logger.error(msg)
        return CommonResponse.error(msg=msg)


def generate_notify_content(notice, status: SiteStatus):
    content = f""
    notice_content_enable = notice.get("notice_content_enable", True)
    if not notice_content_enable:
        return content
    notify_content_item = notice.get("notice_content_item", {
        'level': True,
        'bonus': True,
        'per_bonus': True,
        'score': True,
        'ratio': True,
        'seeding_vol': True,
        'uploaded': True,
        'downloaded': True,
        'seeding': True,
        'leeching': True,
        'invite': True,
        'hr': True
    })

    data = {
        'level': status.my_level,
        'bonus': status.my_bonus,
        'per_bonus': status.bonus_hour,
        'score': status.my_score,
        'ratio': status.ratio,
        'seeding_vol': FileSizeConvert.parse_2_file_size(status.seed_volume),
        'uploaded': FileSizeConvert.parse_2_file_size(status.uploaded),
        'downloaded': FileSizeConvert.parse_2_file_size(status.downloaded),
        'seeding': status.seed,
        'leeching': status.leech,
        'invite': status.invitation,
        'hr': status.my_hr
    }
    chinese_key = {
        'level': '等级',
        'bonus': '魔力',
        'per_bonus': '时魔',
        'score': '做种积分',
        'ratio': '分享率',
        'seeding_vol': '做种量',
        'uploaded': '已上传',
        'downloaded': '已下载',
        'seeding': '做种中',
        'leeching': '下载中',
        'invite': '邀请',
        'hr': 'H&R',
    }

    content += " ".join([f"{chinese_key[key]}：{data[key]}" for key in data if notify_content_item.get(key, True)])

    return content


def sht_reply(session, host: str, cookie: str, user_agent, message: str, fid: int = 95):
    """
    回帖
    :param session:
    :param message: 回帖内容
    :param host:
    :param cookie:
    :param user_agent:
    :param fid: 板块 ID
    :return:
    """
    # 访问综合页面
    zonghe_url = f'{host}/forum.php?mod=forumdisplay&fid={fid}'
    logger.info(f"当前网址：{zonghe_url}")
    response = session.get(
        url=zonghe_url,
        headers={
            "User-Agent": user_agent,
            'Cookie': cookie,
        },
        # cookies=cookie
    )
    logger.debug(f'帖子列表：{response.text}')

    tid_pattern = r'normalthread_(\d+)'
    matches = re.findall(tid_pattern, response.text)
    tid = random.choice(matches)
    page_url = f'{host}/forum.php?mod=viewthread&extra=page%3D1&tid={tid}'
    logger.info(f"当前网址：{page_url}")
    page_response = session.get(
        url=page_url,
        headers={
            "User-Agent": user_agent,
            'Cookie': cookie,
        },
        # cookies=cookie
    )
    logger.debug(f'帖子详情页：{response.text}')

    action_pattern = r'id="fastpostform" action="(.*?)"'
    action_url = re.search(action_pattern, page_response.text).group(1).replace('amp;', '')
    submit_data = {
        "message": message,
        'usesig': '',
        'subject': '',
        'file': '',
    }
    form_object = etree.HTML(response.content.decode("utf-8")).xpath('//form[@id="fastpostform"]')
    # print(etree.tostring(form_object[0]).decode("utf-8"))

    for input in form_object[0].xpath('.//input[@type="hidden"]'):
        submit_data[input.xpath('./@name')[0]] = input.xpath('./@value')[0]

    url = f'{host}/{action_url}&inajax=1'
    logger.info(f"当前网址：{url}")
    logger.info(f"提交数据：{submit_data}")
    headers = {
        'User-Agent': user_agent,
        'Referer': page_url,
        'Cookie': cookie,
        'Accept': '*/*',
        'Host': 'jq2t4.com',
        'Connection': 'keep-alive',
    }
    action_response = session.post(
        url=url,
        headers=headers,
        # cookies=cookie,
        data=submit_data,
    )
    logger.debug(f'回帖：{action_response.text}')
    if action_response.status_code == 200 and action_response.text.find("回复发布成功") > 0:
        logger.info("回帖完成！")
        return CommonResponse.success(msg='回复发布成功')
    else:
        logger.info("回帖出错啦！")
        return CommonResponse.error(msg='回帖出错啦！')


def sht_sign(host, username, password, cookie, user_agent, message: str, fid: int = 95):
    try:
        cookies_dict = cookie2dict(cookie)
        # 登录界面URL
        login_ui_url = f'{host}/member.php?mod=logging&action=login&infloat=yes&handlekey=login&ajaxtarget=fwin_content_login'
        logger.info(login_ui_url)
        # 创建请求对象
        session = requests.Session()
        # 打开登录界面
        response = session.get(
            url=login_ui_url,
            headers={
                "User-Agent": user_agent,
                "Referer": f'{host}/forum.php',
            },
            cookies=cookies_dict
        )
        logger.debug(response.content.decode('utf8'))
        # 检测到签到链接
        # pattern = r'<!\[CDATA\[(.*?)\]\]>'
        # match = re.search(pattern, response.content.decode('utf8'), re.DOTALL)
        # html_code = match.group(1)
        html_code = response.content.decode('utf8').replace('<?xml version="1.0" encoding="utf-8"?>', '').replace(
            '<root><![CDATA[', '').replace(']]></root>', '')
        check_login = etree.HTML(html_code).xpath('//a[@href="plugin.php?id=dd_sign:index"]')
        logger.info(f'Cookie有效检测：签到链接存在数量 {len(check_login)}')
        # 如果检测到签到链接，则直接使用Cookie，否则重新获取Cookie
        if not check_login or len(check_login) <= 0:
            logger.info(f'Cookie失效，重新获取')
            # 解析登录界面数据，获取formhash与loginhash
            html_object = etree.HTML(response.content.decode('utf8')[55:-10])
            # 获取form表单对象
            form = html_object.xpath('//form')[0]
            # 获取提交链接
            login_action_link = form.xpath('@action')[0]
            logger.info(login_action_link)
            # 解析相关字段
            fields = form.xpath('.//input[@type="hidden"]')

            form_data = {
                "formhash": '',
                "referer": f'{host}/forum.php',
                "username": username,
                "password": password,
                "cookietime": 2592000
            }
            # 输出需要填写的字段名和值
            for field in fields:
                name = field.get('name')
                value = field.get('value', '')
                form_data[name] = value
                logger.info(f"字段名: {name}, 值: {value}")

            logger.info(f"登录参数：{form_data}")
            # 登录
            login_action_url = f'{host}{login_action_link}'
            login_response = session.post(
                url=login_action_url,
                data=form_data,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/forum.php",
                },
                cookies={
                    '_safe': 'vqd37pjm4p5uodq339yzk6b7jdt6oich'
                }
            )
            logger.debug(f"登录反馈：{login_response.content.decode('utf8')}")
            cookies_dict = session.cookies.get_dict()
            msg = f"新获取的Cookie：{cookies_dict}"
            logger.info(msg)
            send_text(message=msg, title='请及时更新98Cookie!')
        # 检测签到与否
        check_sign_url = f'{host}/plugin.php?id=dd_sign:index'
        check_sign_response = session.get(
            url=check_sign_url,
            headers={
                "User-Agent": user_agent,
                "Referer": f'{host}/forum.php',
            },
            cookies=cookies_dict,
        )
        check_sign = etree.HTML(check_sign_response.content.decode('utf8')).xpath('//a[contains(text(),"今日已签到")]')
        if not check_sign or len(check_sign) <= 0:
            # 回帖
            reply = sht_reply(session=session, host=host, cookie=cookie, user_agent=user_agent, message=message,
                              fid=fid)
            logger.info(reply.msg)
            if reply.code != 0:
                return reply

            # 打开签到界面
            sign_ui_url = f'{host}/plugin.php?id=dd_sign&mod=sign&infloat=yes&handlekey=pc_click_ddsign&inajax=1&ajaxtarget=fwin_content_pc_click_ddsign'
            # 获取idhash
            sign_response = session.get(
                url=sign_ui_url,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/plugin.php?id=dd_sign:index",
                },
                cookies=cookies_dict,
            )
            logger.info(f'签到界面: {sign_response.content.decode("utf8")}')
            # 使用正则表达式提取字段
            match = re.compile(
                # r'signhash=(.+?)".*name="formhash" value="(\w+)".*name="signtoken" value="(\w+)".*secqaa_(.+?)\"',
                r'signhash=(.+?)".*name="formhash" value="(\w+)".*secqaa_(.+?)\"',
                re.S)
            # signhash, formhash, signtoken, idhash = re.findall(match, sign_response.content.decode('utf8'))[0]
            signhash, formhash, idhash = re.findall(match, sign_response.content.decode('utf8'))[0]
            logger.info(f'签到界面参数: \n链接: {signhash} \n'
                        f' formhash: {formhash} \n signtoken:{None} \n idhash: {idhash}\n')
            # 获取计算题
            calc_ui_url = f'{host}/misc.php?mod=secqaa&action=update&idhash={idhash}&{round(random.uniform(0, 1), 16)}'
            calc_response = session.get(
                url=calc_ui_url,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/plugin.php?id=dd_sign:index",
                },
                cookies=cookies_dict,
            )
            logger.debug(f'计算题: {calc_response.content.decode("utf8")}')
            # 解析签到数据
            pattern = r'(\d+\s*[-+*/]\s*\d+)'
            match = re.search(pattern, calc_response.content.decode('utf8'))
            logger.info(f'解析出的计算题: {match.group(0)}')
            calc_result = eval(match.group(1))
            logger.info(f'计算结果: {calc_result}')
            # 校验签到计算结果
            calc_check_url = f'{host}/misc.php?mod=secqaa&action=check&inajax=1&modid=&idhash={idhash}&secverify={calc_result}'
            logger.info(f"签到检测链接：{calc_check_url}")
            calc_check_response = session.get(
                url=calc_check_url,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/plugin.php?id=dd_sign:index",
                },
                cookies=cookies_dict,
            )
            logger.debug(f"签到校验结果: {calc_check_response.content.decode('utf8')}")
            if 'succeed' in calc_check_response.content.decode('utf8'):
                # 发送签到请求
                sign_form_data = {
                    "formhash": formhash,
                    "signtoken": None,
                    "secqaahash": idhash,
                    "secanswer": calc_result,
                }
                sign_post_url = f'{host}/plugin.php?id=dd_sign&mod=sign&signsubmit=yes&handlekey=pc_click_ddsign&signhash={signhash}&inajax=1'
                logger.info(f"签到链接: {sign_post_url}")
                sign_response = session.post(
                    url=sign_post_url,
                    headers={
                        "User-Agent": user_agent,
                        'referer': f"{host}/plugin.php?id=dd_sign:index",
                    },
                    cookies=cookies_dict,
                    data=sign_form_data,
                )
                logger.debug(f"签到结果页：{sign_response.content.decode('utf8')}")
                match = re.search(r"showDialog\('([^']*)'", sign_response.content.decode('utf8'))
                result = match.group(1)
                logger.info(f'本次签到：{result}')
            elif '已经签到过啦，请明天再来！' in sign_response.content.decode('utf8'):
                result = f't98已经签到过啦！请不要重复签到！'
            else:
                result = f't98签到失败!请检查网页！!'
        else:
            result = f't98已经签到过啦！请不要重复签到！'
            logger.info(result)
        # 检查当前积分与金币
        credit_url = f'{host}/home.php?mod=spacecp&ac=credit&op=base'
        credit_response = session.get(
            url=credit_url,
            headers={
                "User-Agent": user_agent,
                'referer': f"{host}/plugin.php?id=dd_sign:index",
            },
            cookies=cookies_dict,
        )
        logger.debug(f'积分金币页面详情：{credit_response.content.decode("utf8")}')

        pattern = re.compile(
            r'(金钱:\s)*<\/em>(\d+)|(色币:\s)*<\/em>(\d+)|(积分:\s)*<\/em>(\d+)|(评分:\s)*<\/em>(\d+)',
            re.S)
        matches = re.findall(pattern, credit_response.content.decode("utf8"))
        info = '，'.join([''.join(match) for match in matches])
        logger.info(f'积分金币详情: {info}')
        msg = f"本次签到:{result}\n积分金币详情: {info}"

        # 获取当前时间
        now = datetime.now()
        # 计算当天结束的时间
        end_of_day = now.replace(hour=23, minute=59, second=59)
        # 计算当前时间到当天结束的时间间隔
        expiration = end_of_day - now
        cache.set(f"t98_sign_in_state", True, expiration.seconds)
        return CommonResponse.success(msg=msg)

    except Exception as e:
        msg = f'98签到失败：{e}'
        logger.info(traceback.format_exc(8))
        return CommonResponse.error(msg=msg)


def sign_ssd_forum(cookie, user_agent, todaysay):
    try:
        logger.info('SSDForum开始签到')
        # 访问签到页
        sign_url = 'https://ssdforum.org/plugin.php?id=dsu_paulsign:sign'
        sign_response = requests.get(
            url=sign_url,
            headers={
                'User-Agent': user_agent,
                'Referer': 'https://ssdforum.org/',
            },
            cookies=cookie2dict(cookie),
        )
        logger.debug(f'签到页HTML：{sign_response.text}')
        if sign_response.status_code != 200:
            return CommonResponse.error(msg=f'SSDForum签到失败:{sign_response.status_code}')
        html_object = etree.HTML(sign_response.content.decode('gbk'))
        sign_check = html_object.xpath('//div[@class="c"]/text()')
        logger.info(f"签到检测：{sign_check}")
        sign_text = ''
        if not sign_check or len(sign_check):
            logger.info(f"签到检测：{len(sign_check)}")
            # action_url = html_object.xpath('//form[@id="qiandao"]/@action')
            formhash = ''.join(html_object.xpath('//form[@id="qiandao"]/input[@name="formhash"]/@value'))
            # 获取并生成签到参数
            qdxq_options = ['kx', 'ng', 'ym', 'wl', 'nu', 'ch', 'fd', 'yl', 'shuai']
            form_data = {
                'formhash': formhash,
                'qdxq': random.choice(qdxq_options),  # replace with the desired value
                'qdmode': '1',  # replace with the desired value
                'todaysay': todaysay,  # replace with the desired value
            }
            logger.info(f'签到参数：{form_data}')
            # 发送签到请求
            sign_in_url = 'https://ssdforum.org/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1'
            sign_in_response = requests.post(
                url=sign_in_url,
                headers={
                    'User-Agent': user_agent,
                    'Referer': 'https://ssdforum.org/',
                },
                cookies=cookie2dict(cookie),
                data=form_data,
            )
            # 解析签到反馈
            logger.debug(f'签到反馈：{sign_in_response.text}')
            sign_text = ''.join(etree.HTML(sign_in_response.content.decode('gbk')).xpath('//div[@class="c"]/text()'))
        else:
            sign_text = '今日已签到'
            logger.info(sign_text)
        # 获取当前时间
        now = datetime.now()
        # 计算当天结束的时间
        end_of_day = now.replace(hour=23, minute=59, second=59)
        # 计算当前时间到当天结束的时间间隔
        expiration = end_of_day - now
        cache.set(f"sign_ssd_forum_state", True, expiration.seconds)
        sign_response = requests.get(
            url=sign_url,
            headers={
                'User-Agent': user_agent,
                'Referer': 'https://ssdforum.org/',
            },
            cookies=cookie2dict(cookie),
        )
        logger.debug(f"签到页：{sign_response.text}")
        sign_title_rule = '//div[@class="mn"]/h1[1]/text()'
        sign_content_rule = '//div[@class="mn"]/p//text()'
        title = etree.HTML(sign_response.content.decode('gbk')).xpath(sign_title_rule)
        content = etree.HTML(sign_response.content.decode('gbk')).xpath(sign_content_rule)
        result = f'{sign_text}。{"".join(title)} {"".join(content)}'
        logger.info(f'SSDForum签到结果: {result}')
        return CommonResponse.success(msg=result)
    except Exception as e:
        msg = f'SSDForum签到失败，{e}'
        logger.error(traceback.format_exc(5))
        logger.error(msg)
        return CommonResponse.error(msg=msg)


def cnlang_sign(
        username,
        cookie,
        host,
        user_agent
):
    try:
        s = requests.session()
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept - Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'cache-control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Host': host,
            'Cookie': cookie,
            'User-Agent': user_agent
        }

        # 访问Pc主页
        logger.info(host)
        user_info = s.get(
            'https://' + host + '/dsu_paulsign-sign.html?mobile=no',
            headers=headers,
            cookies=cookie2dict(cookie)
        ).text
        user_name = re.search(r'title="访问我的空间">(.*?)</a>', user_info)

        # 解析 HTML 页面
        # soup = BeautifulSoup(html, 'html.parser')
        tree = etree.HTML(user_info)

        # 找到 name 为 formhash 的 input 标签
        # formhash_input = soup.find('input', {'name': 'formhash'})
        formhash_value = ''.join(tree.xpath('//input[@name="formhash"]/@value'))

        # 从 input 标签中提取 formhash 的值
        # formhash_value = re.search(r'value="(.+?)"', str(formhash_input)).group(1)

        logger.info("formhash：" + formhash_value)
        # 随机获取心情
        xq = s.get('https://v1.hitokoto.cn/?encode=text').text
        # 保证字数符合要求
        logger.info("想说的话：" + xq)
        while (len(xq) < 6 | len(xq) > 50):
            xq = s.get('https://v1.hitokoto.cn/?encode=text').text
            logger.info("想说的话：" + xq)
        if user_name:
            logger.info("登录用户名为：" + user_name.group(1))
            logger.info("环境用户名为：" + username)
        else:
            logger.info("未获取到用户名")
        if user_name is None or (user_name.group(1) != username):
            raise Exception("【国语视界】cookie失效")
        # 获取签到链接,并签到
        qiandao_url = 'plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1'

        # 签到
        payload = dict(formhash=formhash_value, qdxq='kx', qdmode='1', todaysay=xq, fastreply='0')
        logger.info(f"form_data: {payload}")
        qdjg = s.post(
            'https://' + host + '/' + qiandao_url,
            headers=headers,
            data=payload,
            cookies=cookie2dict(cookie)
        ).text

        # soup = BeautifulSoup(html, 'html.parser')
        # div = soup.find('div', {'class': 'c'})  # 找到 class 为 clash，id 为 c 的 div
        # content = div.text  # 获取 div 的文本内容
        content = ''.join(etree.HTML(qdjg).xpath('//div[@class="c"]/text()'))

        logger.info(content)
        # 获取当前时间
        now = datetime.now()
        # 计算当天结束的时间
        end_of_day = now.replace(hour=23, minute=59, second=59)
        # 计算当前时间到当天结束的时间间隔
        expiration = end_of_day - now
        cache.set(f"cnlang_sign_state", True, expiration.seconds)
        # 获取积分
        user_info = s.get(
            'https://' + host + '/home.php?mod=spacecp&ac=credit&showcredit=1&inajax=1&ajaxtarget=extcreditmenu_menu',
            headers=headers,
            cookies=cookie2dict(cookie)
        ).text
        current_money = re.search(r'<span id="hcredit_2">(\d+)</span>', user_info).group(1)
        log_info = f'clang 签到：{content} 当前大洋余额：{current_money}'
        logger.info(log_info)
        # send("签到结果", log_info)
        return CommonResponse.success(msg=log_info)
    except Exception as e:
        msg = f'clang签到失败，失败原因: {e}'
        logger.error(msg)
        logger.error(traceback.format_exc(5))
        return CommonResponse.error(msg=msg)


def get_time_join(my_site, details_html):
    site = get_object_or_404(WebSite, id=my_site.site)
    mirror = my_site.mirror if my_site.mirror_switch else site.url
    try:
        if 'greatposterwall' in site.url or 'dicmusic' in site.url:
            logger.debug(details_html)
            details_response = details_html.get('response')
            stats = details_response.get('stats')
            my_site.time_join = stats.get('joinedDate')
            my_site.latest_active = stats.get('lastAccess')
            my_site.save()
        elif "m-team" in mirror:
            pass
        elif 'zhuque.in' in site.url:
            my_site.time_join = datetime.fromtimestamp(details_html.get(site.my_time_join_rule))
            my_site.save()
        else:
            logger.debug(f'注册时间：{details_html.xpath(site.my_time_join_rule)}')
            if site.url in [
                'https://monikadesign.uk/',
                'https://pt.hdpost.top/',
                'https://reelflix.xyz/',
            ]:
                time_str = ''.join(details_html.xpath(site.my_time_join_rule))
                time_str = re.sub(u"[\u4e00-\u9fa5]", "", time_str).strip()
                time_join = datetime.strptime(time_str, '%b %d %Y')
                logger.debug(f'注册时间：{time_join}')
                my_site.time_join = time_join
            elif site.url in [
                'https://hd-torrents.org/',
            ]:
                my_site.time_join = datetime.strptime(
                    ''.join(details_html.xpath(site.my_time_join_rule)).replace('\xa0', ''),
                    '%d/%m/%Y %H:%M:%S'
                )
            elif site.url in [
                'https://hd-space.org/',
            ]:
                my_site.time_join = datetime.strptime(
                    ''.join(details_html.xpath(site.my_time_join_rule)).replace('\xa0', ''),
                    '%B %d, %Y,%H:%M:%S'
                )
            elif site.url in [
                'https://jpopsuki.eu/',
            ]:
                my_site.time_join = datetime.strptime(
                    ''.join(details_html.xpath(site.my_time_join_rule)).replace('\xa0', ''),
                    '%b %d %Y, %H:%M'
                )
            elif site.url in [
                'https://www.torrentleech.org/',
            ]:
                my_site.time_join = dateutil.parser.parse(''.join(details_html.xpath(site.my_time_join_rule)))
            elif site.url in [
                'https://exoticaz.to/',
                'https://cinemaz.to/',
                'https://avistaz.to/',
            ]:
                time_str = ''.join(details_html.xpath(site.my_time_join_rule)).split('(')[0].strip()
                my_site.time_join = datetime.strptime(time_str, '%d %b %Y %I:%M %p')
            else:
                time_join = re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', ''.join(
                    details_html.xpath(site.my_time_join_rule)
                ).strip())
                my_site.time_join = ''.join(time_join)
            my_site.latest_active = datetime.now()
            my_site.save()
    except Exception as e:
        msg = f'🆘 {site.name} 注册时间获取出错啦！'
        logger.error(msg)
        logger.error(traceback.format_exc(3))


def sync_cookie_from_cookie_cloud(server: str, key: str, password: str):
    """
    同步 cookie
    :param server:
    :param key:
    :param password:
    :return:
    """
    try:
        helper = CookieCloudHelper(server=server, key=key, password=password)
        res = helper.download()
        if res.code != 0:
            return res
        website_list = WebSite.objects.all()
        msg_list = []
        count_created = 0
        count_updated = 0
        count_failed = 0
        for domain, cookie in res.data.items():
            try:
                website = website_list.filter(alive=True).get(url__contains=domain)
                mysite, created = MySite.objects.update_or_create(site=website.id, defaults={"cookie": cookie})

                if created:
                    mysite.nickname = website.name
                    mysite.save()
                    count_created += 1
                    msg = f'- {mysite.nickname} 站点添加成功！\n'
                    logger.info(f'开始获取 UID，PASSKEY，注册时间')
                    try:
                        scraper = cloudscraper.create_scraper(browser={
                            'browser': 'chrome',
                            'platform': 'darwin',
                        })
                        response = scraper.get(
                            url=website.url + website.page_control_panel,
                            cookies=cookie2dict(cookie),
                        )
                        logger.debug(f'控制面板页面：{response.text}')
                        html_object = etree.HTML(response.content)
                        mysite.user_id = ''.join(html_object.xpath(website.my_uid_rule)).split('=')[-1]
                        mysite.passkey = ''.join(html_object.xpath(website.my_passkey_rule))
                        get_time_join(mysite, html_object)
                        mysite.save()
                        logger.debug(f'uid:{mysite.user_id}')
                        logger.debug(f'passkey:{mysite.passkey}')
                    except Exception as e:
                        msg += f'获取 UID，PASSKEY或注册时间失败！请手动获取！{e}'
                else:
                    msg = f'- {mysite.nickname} 站点更新成功！\n'
                    count_updated += 1
                logger.info(msg)
                msg_list.append(msg)
            except Exception as e:
                logger.error(f'尚不支持或此站点已关闭：{domain} ')
                count_failed += 1
                continue
        msg = f'> 本次同步任务共添加站点：{count_created}, 更新站点：{count_updated}, 失败站点：{count_created}\n'
        logger.info(msg)
        msg_list.insert(0, msg)
        return CommonResponse.success(msg=''.join(msg_list))
    except Exception as e:
        return CommonResponse.error(msg=f'同步 Cookie 出错啦！{e}')


def push_torrents_to_sever(push_once: int):
    """
    上传本地种子到服务器
    :param push_once: 单词上传数据量
    :return:
    """
    try:
        # 从数据库读取hash 不为空的种子
        torrents = TorrentInfo.objects.filter(pushed=False).exclude(hash_string__exact='')
        logger.info(f'当前共有符合条件的种子：{len(torrents)}')
        if len(torrents) <= 0:
            return f"当前没有需要推送的种子！"
        # 推送到服务器
        msg = []
        while torrents:
            chunks = torrents[:push_once]  # 从消息中截取最大长度的部分
            try:
                torrent_list = [t.to_dict(exclude=['id']) for t in chunks]
                logger.debug(torrent_list[0])
                logger.debug(torrents)
                res = requests.post(
                    url=f"{os.getenv('REPEAT_SERVER')}/api/website/torrents/multiple",
                    json=torrent_list,
                    headers={
                        "content-type": "application/json",
                        "AUTHORIZATION": os.getenv("TOKEN"),
                        "EMAIL": os.getenv("DJANGO_SUPERUSER_EMAIL"),
                    }
                )

                # 已存档的种子更新状态为6==已推送到服务器
                logger.info(res.text)
                if res.status_code == 200:
                    torrents = torrents[push_once:]
                    TorrentInfo.objects.filter(id__in=[t.id for t in chunks]).update(pushed=True)
                    msg.append(f"成功上传 {len(chunks)} 条种子信息")
                else:
                    msg.append(f"{len(chunks)} 条种子信息上传失败！")
            except Exception as e:
                err_msg = f'推送种子信息到服务器失败！{e}'
                logger.error(err_msg)
                msg.append(msg)
                logger.error(traceback.format_exc(5))
        logger.info(msg)
        return '\n'.join(msg)
    except Exception as e:
        msg = f'推送种子信息到服务器失败！{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(5))
        return msg


def calculate_expiry_time_from_string(time_str):
    """
    解析mteam免费时间
    :param time_str:
    :return:
    """

    def parse_remaining_time(time_str: str):
        time_str.replace("時", "时").replace("天", "日")
        # 检查是否是 "X 日 X 時" 格式
        if "日" in time_str and "时" in time_str:
            days = int(re.search(r"(\d+)\s*日", time_str).group(1))
            hours = int(re.search(r"(\d+)\s*时", time_str).group(1))
            return days, hours, 0

        # 检查是否是 "X 時 X 分" 格式
        elif "时" in time_str and "分" in time_str:
            hours = int(re.search(r"(\d+)\s*时", time_str).group(1))
            minutes = int(re.search(r"(\d+)\s*分", time_str).group(1))
            return 0, hours, minutes

        # 检查是否是 "X 分" 格式
        elif "分" in time_str:
            minutes = int(re.search(r"(\d+)\s*分", time_str).group(1))
            return 0, 0, minutes

        else:
            raise ValueError("无法解析时间字符串")

    def calculate_expiry_time(days: int, hours: int, minutes: int):
        # 获取当前日期和时间
        current_time = datetime.now()

        # 计算剩余时间的时间差
        time_difference = timedelta(days=days, hours=hours, minutes=minutes)

        # 计算到期时间

        return current_time + time_difference

    # 解析字符串并计算到期时间
    days, hours, minutes = parse_remaining_time(time_str)
    expiry_time = calculate_expiry_time(days, hours, minutes)

    return expiry_time
