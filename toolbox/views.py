import hashlib
import json
import logging
import os
import random
import re
import subprocess
import time
import traceback
from datetime import datetime, timedelta
from typing import List, Union

import aip
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
from lxml import etree
from pypushdeer import PushDeer
from telebot import apihelper

from auxiliary.base import DownloaderCategory
from auxiliary.settings import BASE_DIR
from configuration.models import PushConfig
from download.models import Downloader
from my_site.models import SiteStatus, TorrentInfo, MySite
from toolbox.schema import CommonResponse, DotDict
from website.models import WebSite
from .wechat_push import WechatPush
from .wxpusher import WxPusher

# Create your views here.
logger = logging.getLogger('ptools')


def parse_toml(cmd) -> dict:
    """从配置文件解析获取相关项目"""
    data = toml.load('db/ptools.toml')
    return data.get(cmd)


def check_token(token) -> bool:
    own_token = parse_toml('token').get('token')
    logger.info(f'{own_token}=={token}')
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
        result = subprocess.run(['supervisorctl', 'shutdown'], check=True, text=True, capture_output=True)
        logger.debug(f'Successfully executed command: {result.stdout}')
        return '您的软件未经授权，如果您喜欢本软件，欢迎付费购买授权或申请临时授权。'
    res = requests.get('http://api.ptools.fun/neice/check', params={
        "token": token,
        "email": os.getenv("DJANGO_SUPERUSER_EMAIL", None)
    })
    if res.status_code == 200 and res.json().get('code') == 0:
        return res.json().get('msg')
    else:
        return '您的软件使用授权到期了！如果您喜欢本软件，欢迎付费购买授权或申请临时授权。'


def send_text(message: str, title: str = '', url: str = None):
    """通知分流"""
    notifies = parse_toml("notify")
    res = '你还没有配置通知参数哦！'
    try:
        message = f'{verify_token()}\n{"*" * 30}\n{message}'
        pass
    except Exception as e:
        msg = f'授权验证失败！'
        logger.error(msg)
        return msg
    if len(notifies) <= 0:
        return res
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
                res = notify_push.send_text(
                    text=message,
                    to_uid=notify.get('to_uid', '@all')
                )
                msg = '企业微信通知：{}'.format(res)
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
                if len(message) <= max_length:
                    bot.send_message(telegram_chat_id, message)  # 如果消息长度不超过最大限制，直接发送消息
                else:
                    while message:
                        chunk = message[:max_length]  # 从消息中截取最大长度的部分
                        bot.send_message(telegram_chat_id, chunk, parse_mode="Markdown")  # 发送消息部分
                        message = message[max_length:]  # 剩余部分作为新的消息进行下一轮发送

                msg = 'Telegram通知成功'
                logger.info(msg)

        except Exception as e:
            msg = f'通知发送失败，{res} {traceback.format_exc(limit=5)}'
            logger.error(msg)


def get_git_log(branch='master', n=5):
    repo = git.Repo(path='.')
    # 拉取仓库更新记录元数据
    repo.remote().set_url('git@github.com:ngfchl/NewPtools.git')
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
        torrents.append({
            'hash_string': article.id,
            'title': article.title,
            'tid': (article.link.split('=')[-1]),
            'size': article.links[-1].get('length'),
            'published': datetime.fromtimestamp(time.mktime(article.published_parsed)),
        })
    return torrents


def get_downloader_instance(downloader_id):
    """根据id获取下载实例"""
    try:
        downloader = Downloader.objects.filter(id=downloader_id).first()
        if downloader.category == DownloaderCategory.qBittorrent:
            client = qbittorrentapi.Client(
                host=downloader.host,
                port=downloader.port,
                username=downloader.username,
                password=downloader.password,
                SIMPLE_RESPONSES=True,
                REQUESTS_ARGS={
                    'timeout': (3.1, 30)
                }
            )
            client.auth_log_in()
        else:
            client = transmission_rpc.Client(
                host=downloader.host, port=downloader.port,
                username=downloader.username, password=downloader.password
            )
        return client, downloader.category
    except Exception as e:
        logger.error(traceback.format_exc(3))
        logger.exception(f'下载器连接失败：{e}')
        return None, None


def get_downloader_speed(downloader: Downloader):
    """获取单个下载器速度信息"""
    try:
        client, _ = get_downloader_instance(downloader.id)
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
            urls=urls,
            category=category,
            save_path=save_path,
            is_skip_checking=is_skip_checking,
            is_paused=is_paused,
            upload_limit=upload_limit * 1024,
            download_limit=download_limit * 1024,
            use_auto_torrent_management=use_auto_torrent_management,
            cookie=cookie
        )
        if res == 'Ok.':
            return CommonResponse.success(msg=f'种子已添加，请检查下载器！{res}')
        return CommonResponse.error(msg=f'种子添加失败！{res}')
    if downloader_category == DownloaderCategory.Transmission:
        # res = client.add_torrent(
        #     torrent=urls,
        #     labels=category,
        #     paused=is_paused,
        #     cookies=cookie
        # )
        # if res.hashString and len(res.hashString) >= 0:
        #     return CommonResponse.success(msg=f'种子已添加，请检查下载器！{res.name}')
        return CommonResponse.error(msg=f'种子添加失败！暂不支持Transmission！')


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


def filter_torrent_by_rules(my_site: MySite, torrents: List[TorrentInfo]):
    """
    使用站点选中规则筛选种子
    :param my_site: 我的站点
    :param torrents: 种子列表
    :return: 筛选过后的种子列表
    """
    rules = json.loads(my_site.remove_torrent_rules).get('push')
    logger.info(f"当前站点：{my_site.nickname}, 选种规则：{rules}")
    torrent_list = []
    for torrent in torrents:
        try:
            push_flag = False
            # 发种时间命中
            published = rules.get('published')
            if published:
                if isinstance(torrent.published, str):
                    torrent_published = datetime.strptime(torrent.published, "%Y-%m-%d %H:%M:%S").timestamp()
                else:
                    torrent_published = torrent.published.timestamp()
                push_flag = time.time() - torrent_published < published
            logger.info(f"{my_site.nickname} {torrent.tid} 发种时间命中：{push_flag}")
            if not push_flag:
                torrent.state = 5
                torrent.save()
                continue
            # 做种人数命中
            seeders = rules.get('seeders')
            if seeders:
                push_flag = torrent.seeders < seeders
            logger.info(f"{my_site.nickname} {torrent.tid} 做种人数命中：{push_flag}")
            if not push_flag:
                torrent.state = 5
                torrent.save()
                continue
            # 下载人数命中
            leechers = rules.get('leechers')
            if leechers:
                push_flag = torrent.leechers > leechers
            logger.info(f"{my_site.nickname} {torrent.tid} 下载人数命中：{push_flag}")
            if not push_flag:
                torrent.state = 5
                torrent.save()
                continue
            # 剩余免费时间
            sale_expire = rules.get('sale_expire')
            if sale_expire:
                if isinstance(torrent.published, str):
                    torrent_published = datetime.strptime(torrent.published, "%Y-%m-%d %H:%M:%S").timestamp()
                else:
                    torrent_published = torrent.published.timestamp()
                push_flag = time.time() - torrent_published < sale_expire
            logger.info(f"{my_site.nickname} {torrent.tid} 剩余免费时间命中：{push_flag}")
            if not push_flag:
                torrent.state = 5
                torrent.save()
                continue
            # 要刷流的种子大小
            size = rules.get('size')
            if size:
                min_size = size.get('min')
                max_size = size.get('max')
                push_flag = min_size < torrent.size / 1024 / 1024 / 1024 < max_size
                logger.info(f"{my_site.nickname} {torrent.tid} 种子大小命中：{push_flag}")
            if not push_flag:
                torrent.state = 5
                torrent.save()
                continue
            # 包含关键字命中
            if rules.get('include'):
                for rule in rules.get('include'):
                    if torrent.title.find(rule) > 0:
                        push_flag = True
                        break
                logger.info(f"{my_site.nickname} {torrent.tid} 包含关键字命中：{push_flag}")
            if not push_flag:
                torrent.state = 5
                torrent.save()
                continue
            # 排除关键字命中
            if rules.get('exclude'):
                for rule in rules.get('exclude'):
                    if torrent.title.find(rule) > 0:
                        push_flag = False
                        break
                logger.info(f"{my_site.nickname} {torrent.tid} 排除关键字命中：{push_flag}")
            if not push_flag:
                torrent.state = 5
                torrent.save()
                continue
            torrent_list.append(torrent)
        except Exception as e:
            logger.error(traceback.format_exc(3))
            continue
    return torrent_list


def sha1_hash(string: str) -> str:
    return hashlib.sha1(string.encode()).hexdigest()


def get_hash_by_category(client, torrent_info, category):
    try:
        # 如果已经获取到了哈希值则直接计算文件列表哈希值和块哈希值并保存
        if torrent_info.hash_string and torrent_info.pieces_qb and torrent_info.filelist:
            return CommonResponse.error(msg=f'{torrent_info.title}: 无需完善！')
            # 如果没有哈希值，就通过qbittorrentapi客户端获取种子列表
        if not torrent_info.hash_string:
            t = client.torrents_info(category=category)
            if len(t) == 0:
                return CommonResponse.error(msg=f'{torrent_info.title}: 查看种子列表失败！')
            # 遍历种子列表，寻找匹配的种子文件
            torrent_hash = None
            if len(t) == 1:
                torrent_hash = t[0]['hash']
            # 如果没有找到匹配的种子文件，输出错误信息
            if not torrent_hash:
                return CommonResponse.error(msg=f'{torrent_info.title}: 查找种子失败！找到 {len(t)} 个种子!')
            torrent_info.hash_string = torrent_hash
            torrent_info.save()
        # 通过qbittorrentapi客户端获取种子的块哈希列表和文件列表，并转换为字符串
        if not torrent_info.pieces_qb:
            # 获取种子块HASH列表，并生成种子块HASH列表字符串的sha1值，保存
            pieces_hash_list = client.torrents_piece_hashes(torrent_hash=torrent_info.hash_string)
            pieces_hash_string = ''.join(str(pieces_hash) for pieces_hash in pieces_hash_list)
            torrent_info.pieces_qb = sha1_hash(pieces_hash_string)
        if not torrent_info.filelist:
            # 获取文件列表，并生成文件列表字符串的sha1值，保存
            file_list = client.torrents_files(torrent_hash=torrent_info.hash_string)
            file_list_hash_string = ''.join(str(item) for item in file_list)
            torrent_info.filelist = sha1_hash(file_list_hash_string)
            torrent_info.files_count = len(file_list)
        torrent_info.save()
        return CommonResponse.success(msg=f'{torrent_info.title}: 完善种子信息成功！')
    except qbittorrentapi.exceptions.NotFound404Error:
        msg = f'{torrent_info.title}: 完善信息失败!--下载器已删种！'
        torrent_info.state = 3
        torrent_info.save()
        return CommonResponse.error(msg=msg)
    except Exception as e:
        msg = f'{torrent_info.title}: 完善信息失败！'
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=f'{msg}-- {e}')


def remove_torrent_by_site_rules(my_site: MySite):
    """
    站点删种
    :param my_site:
    :return msg
    """
    logger.info(f"当前站点：{my_site}, 删种规则：{my_site.remove_torrent_rules}")
    rules = json.loads(my_site.remove_torrent_rules).get('remove')
    logger.info(f"当前下载器：{my_site.downloader_id}")
    client, _ = get_downloader_instance(my_site.downloader.id)
    if not client:
        return CommonResponse.error(msg=f'{my_site.nickname} - {my_site.downloader.name} 链接失败!')
    website = WebSite.objects.get(id=my_site.site)
    count = 0
    hashes = []
    expire_hashes = []
    for torrent_info in my_site.torrentinfo_set.filter(state__lt=3):
        try:
            # 完善种子信息
            category = f'{website.nickname}-{torrent_info.tid}'
            res = get_hash_by_category(client, torrent_info, category)
            if res.code == -1:
                logger.error(res.msg)
            logger.debug(res.msg)
            count += 1
            # 删种规则
            hash_string = torrent_info.hash_string
            logger.debug(f'{hash_string} -- {torrent_info.title}')
            if not hash_string:
                logger.debug(f'{torrent_info.title} 未抓取到种子HASH')
                continue
            torrent = client.torrents_info(torrent_hashes=hash_string)
            if len(torrent) != 1:
                logger.error(f'{hash_string} - 出错啦，未找到符合条件的种子')
                continue
            else:
                torrent = torrent[0]
            prop = client.torrents_properties(torrent_hash=hash_string)
            # 排除关键字命中，
            delete_flag = False
            if rules.get('exclude'):
                for rule in rules.get('exclude'):
                    if torrent.title.find(rule) > 0:
                        delete_flag = True
                        break
                logger.info(f"{my_site.nickname} {torrent.tid} 排除关键字命中：{delete_flag}")
            if delete_flag:
                # 遇到要排除的关键字的种子，直接跳过，不再继续执行删种
                continue
            # 免费到期检测
            if not torrent_info.sale_expire:
                logger.info(f'{torrent_info.title} 免费过期时间：{torrent_info.sale_expire}')
            else:
                torrent_sale_expire = torrent_info.sale_expire.timestamp()
                sale_expire = rules.get('sale_expire', {"expire": 300, "delete_on_completed": True})
                expire_time = sale_expire.get('expire', 300)
                delete_flag = sale_expire.get('delete_on_completed')
                if time.time() - torrent_sale_expire <= expire_time and (prop.get('completion_date') < 0 or (
                        prop.get('completion_date') > 0 and delete_flag)):
                    expire_hashes.append(hash_string)
                    logger.debug(f'{torrent_info.title} 免费即将到期 命中')
                    continue
            # 指定时间段内平均速度
            upload_speed_avg = rules.get("upload_speed_avg")
            logger.debug(f'指定时间段内平均速度检测: {upload_speed_avg}')
            if upload_speed_avg:
                time_delta = time.time() - torrent_info.updated_at.timestamp()
                if time_delta < upload_speed_avg.get("time"):
                    pass
                else:
                    uploaded_eta = prop.get('total_uploaded') - torrent_info.uploaded
                    uploaded_avg = uploaded_eta / time_delta
                    logger.debug(f'{torrent_info.title} 上传速度 {uploaded_avg / 1024} ')
                    if uploaded_avg < upload_speed_avg.get("upload_speed") * 1024:
                        logger.debug(f'< {upload_speed_avg.get("upload_speed")} 不达标删种 命中')
                        hashes.append(hash_string)
                        continue
                    else:
                        torrent_info.uploaded = prop.get('total_uploaded')
                        torrent_info.save()
            logger.debug(f'{hash_string} -- {torrent_info.title} 上传速度不达标删种 未命中')
            logger.debug(f'站点删种检测')
            not_registered_msg = [
                'torrent not registered with this tracker',
                'err torrent deleted due to other',
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
                logger.debug(f'{hash_string} -- {torrent_info.title} 站点删种 命中')
                torrent_info.state = 4
                torrent_info.save()
                continue
            else:
                logger.debug(f'{hash_string} -- {torrent_info.title} 站点删种 未命中')
            # 完成人数超标删除
            torrent_num_complete = rules.get("num_completer")
            logger.debug(f'{hash_string} -- {torrent_info.title} 完成人数超标删除: {torrent_num_complete}')
            if torrent_num_complete:
                completers = torrent_num_complete.get("completers")
                upspeed = torrent_num_complete.get("upspeed")
                num_complete = prop.get('seeds_total')
                if num_complete > completers and torrent.get("upspeed") < upspeed:
                    logger.debug(f'{hash_string} -- {torrent_info.title} 完成人数超标,当前速度不达标 命中')
                    hashes.append(hash_string)
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 完成人数未超标 未命中')
            # 正在下载人数 低于设定值删除
            torrent_num_incomplete = rules.get("num_incomplete")
            logger.debug(f'完成人数超标删除: {torrent_num_incomplete}')
            if torrent_num_incomplete and torrent_num_incomplete > 0:
                num_incomplete = torrent.get('num_incomplete')
                logger.debug(f'{hash_string} -- {torrent_info.title} 正在下载完成人数不达标: {num_incomplete}')
                if num_incomplete < torrent_num_incomplete:
                    logger.debug(f'{hash_string} -- {torrent_info.title} 正在下载人数 低于设定值 命中')
                    hashes.append(hash_string)
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 正在下载人数 高于设定值 未命中')
            # 无上传无下载超时删种
            logger.debug(f'完成人数超标删除: {rules.get("timeout") and rules.get("timeout") > 0}')
            if rules.get("timeout") and rules.get("timeout") > 0:
                last_activity = torrent.get('last_activity')
                logger.debug(f'{hash_string} -- {torrent_info.title} 最后活动时间: {time.time() - last_activity}')
                if time.time() - last_activity > rules.get("timeout"):
                    logger.debug(f'{hash_string} -- {torrent_info.title} 无活动超时 命中')
                    hashes.append(hash_string)
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 无活动超时 未命中')
            # 进度与平均上传速度达标检测
            progress = prop.get('pieces_have') / prop.get('pieces_num')
            progress_check = rules.get("progress_check")
            logger.debug(f'进度与平均上传速度达标检测: {progress_check}')
            if progress_check and len(progress_check) > 0:
                progress_checked = False
                for key, value in progress_check.items():
                    logger.debug(
                        f'{hash_string}-{torrent_info.title} 指定进度{float(key)},'
                        f'指定速度{value * 1024},平均上传速度: {prop.get("up_speed_avg")}'
                    )
                    if progress >= float(key) and prop.get('up_speed_avg') < value * 1024:
                        hashes.append(hash_string)
                        progress_checked = True
                        logger.debug(
                            f'{hash_string} -- {torrent_info.title} 指定进度与平均上传速度达标检测 低于设定值 命中')
                        break
                if progress_checked:
                    continue
                logger.debug(f'{hash_string} -- {torrent_info.title} 指定进度与平均上传速度达标检测 高于设定值 未命中')
            # 达到指定分享率
            ratio = prop.get('share_ratio')
            if rules.get("max_ratio") and ratio >= rules.get("max_ratio"):
                hashes.append(hash_string)
                logger.debug(f'{hash_string} -- {torrent_info.title} 已达到指定分享率 命中')
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
                    if time_active >= float(key) and ratio < value:
                        logger.debug(f'{hash_string} -- {torrent_info.title} 指定时间段内分享率不达标 低于设定值 命中')
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
        f'{my_site.nickname}-本次运行完善{count}个种子信息！删种规则命中任务:{len(hashes)}个，免费即将到期命中：{len(expire_hashes)}个')
    try:
        count = 0
        if len(hashes) + len(expire_hashes) > 0:
            client.torrents_reannounce(torrent_hashes=hashes)
            # 单次最多删种数量, 不填写默认5, 免费到期的不算在内
            num_delete = rules.get("num_delete", None)
            random.shuffle(hashes)
            hashes = hashes[:num_delete]
            hashes.extend(expire_hashes)
            client.torrents_delete(torrent_hashes=hashes, delete_files=True)
            # 对已删除的种子信息进行归档
            count = TorrentInfo.objects.filter(
                hash_string__in=hashes
            ).update(state=5, downloader=None)
            msg = f'{my_site.nickname}：本次运行删除种子{count}个！'
        else:
            msg = f'{my_site.nickname}：本次运行没有种子要删除！'
        logger.info(msg)
        return CommonResponse.success(msg=msg, data=count)
    except Exception as e:
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=f'{my_site.nickname} - 删种出错啦！')


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
        url = 'http://api.iyuu.cn/index.php?s=App.Api.Hash'
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
        logger.info(f'辅种返回消息码：{ret}，返回消息：{res.get("msg")}')
        if ret == 200:
            return CommonResponse.success(data=res.get('data'))
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


def sht_sign(host, username, password, cookie, user_agent):
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
        pattern = r'<!\[CDATA\[(.*?)\]\]>'
        match = re.search(pattern, response.content.decode('utf8'), re.DOTALL)
        html_code = match.group(1)
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
                r'signhash=(.+?)".*name="formhash" value="(\w+)".*name="signtoken" value="(\w+)".*secqaa_(.+?)\"',
                re.S)
            signhash, formhash, signtoken, idhash = re.findall(match, sign_response.content.decode('utf8'))[0]
            logger.info(f'签到界面参数: \n链接: {signhash} \n'
                        f' formhash: {formhash} \n signtoken:{signtoken}\n idhash: {idhash}\n')
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
                    "signtoken": signtoken,
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
