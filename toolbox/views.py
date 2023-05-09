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
import jwt
import qbittorrentapi
# import git
import requests
import toml as toml
import transmission_rpc
from django.conf import settings
from pypushdeer import PushDeer
from wxpusher import WxPusher

from auxiliary.base import PushConfig, DownloaderCategory
from auxiliary.settings import BASE_DIR
from download.models import Downloader
from my_site.models import SiteStatus, TorrentInfo, MySite
from toolbox.models import BaiduOCR, Notify
from toolbox.schema import CommonResponse
from .wechat_push import WechatPush

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


# def get_git_log(branch, n=20):
#     repo = git.Repo(path='.')
#     # 拉取仓库更新记录元数据
#     repo.remote().fetch()
#     # commits更新记录
#     logger.info('当前分支{}'.format(branch))
#     return [{
#         'date': log.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
#         'data': log.message,
#         'hexsha': log.hexsha[:16],
#     } for log in list(repo.iteipr_commits(branch, max_count=n))]


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
    for notify in notifies:
        try:
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
        # print(article.published).get('enclosure').get('url'))
        # print(time.strftime('%Y-%m-%d %H:%M:%S', article.published_parsed))
        torrents.append({
            'hash_string': article.id,
            'title': article.title,
            'tid': (article.link.split('=')[-1]),
            'size': article.links[-1].get('length'),
            'published': time.mktime(article.published_parsed),
        })
    return torrents


def get_torrents_hash_from_iyuu(iyuu_token: str, hash_list: List[str]):
    # hash_list = get_hashes()
    hash_list.sort()
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
        'version': '2.0.0',
        # hash列表
        'hash': hash_list_json,
        # hash列表sha1
        'sha1': hash_list_sha1
    }
    res = requests.post(url=url, data=data).json()
    logger.info(res)
    ret = res.get('ret')
    if ret == 200:
        return CommonResponse.success(data=res.get('data'))
    return CommonResponse.error(msg=res.get('msg'))


def get_downloader_instance(downloader_id):
    """根据id获取下载实例"""
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


def get_downloader_speed(downloader: Downloader):
    """获取单个下载器速度信息"""
    try:
        client, _ = get_downloader_instance(downloader.id)
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
        downloader_id: int,
        urls: Union[List[str], str],
        category: str = '',
        cookie: str = '',
        upload_limit: int = 0,
        download_limit: int = 0,
        is_skip_checking: bool = None,
        is_paused: bool = None,
        use_auto_torrent_management: bool = None,

):
    """将辅种数据推送至下载器"""
    client, downloader_category = get_downloader_instance(downloader_id)
    # 暂停模式推送至下载器（包含参数，下载链接，Cookie，分类或者下载路径）
    # 开始校验
    # 验证校验结果，不为百分百的，暂停任务
    if downloader_category == DownloaderCategory.qBittorrent:
        res = client.torrents.add(
            urls=urls,
            category=category,
            is_skip_checking=is_skip_checking,
            is_paused=is_paused,
            upload_limit=upload_limit,
            download_limit=download_limit,
            use_auto_torrent_management=use_auto_torrent_management,
            cookie=cookie
        )
        if res == 'Ok.':
            return CommonResponse.success(msg=f'种子已添加，请检查下载器！{res}')
        return CommonResponse.error(msg=f'种子添加失败！{res}')
    if downloader_category == DownloaderCategory.Transmission:
        res = client.add_torrent(
            torrent=urls,
            labels=category,
            paused=is_paused,
            cookies=cookie
        )
        if res.hashString and len(res.hashString) >= 0:
            return CommonResponse.success(msg=f'种子已添加，请检查下载器！{res.name}')
        return CommonResponse.error(msg=f'种子添加失败！')


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
            logger.info('拆包完成')
        else:
            logger.info('无需拆包？？？')


def remove_torrent_by_site_rules(my_site_id: int, hash_list: List[str] = []):
    """
    站点删种
    :param my_site_id:
    :param hash_list:
    :return msg
    """
    my_site = MySite.objects.get(id=my_site_id)
    logger.info(f"当前站点：{my_site}, 删种规则：{my_site.remove_torrent_rules}")
    rules = json.loads(my_site.remove_torrent_rules)
    torrent_infos = TorrentInfo.objects.filter(site=my_site, state=True).all()
    client, _ = get_downloader_instance(my_site.downloader.id)
    if hash_list and len(hash_list) <= 0:
        hash_list = [torrent_info.hash_string for torrent_info in torrent_infos]
    torrents = client.torrents_info(torrent_hashes=hash_list)
    hashes = []
    for torrent in torrents:
        hash_string = torrent.get('hash')
        prop = client.torrents_properties(torrent_hash=hash_string)
        if prop:
            # 指定时间段内平均速度
            upload_speed_avg = rules.get("upload_speed_avg")
            if upload_speed_avg:
                torrent_info = torrent_infos.filter(hash_string=hash_string).first()
                if torrent_info:
                    time_delta = time.time() - torrent_info.updated_at.timestamp()
                    if time_delta < upload_speed_avg.get("time"):
                        continue
                    uploaded_eta = (prop.get('total_uploaded') - torrent_info.uploaded)
                    uploaded_avg = uploaded_eta / time_delta
                    if uploaded_avg < upload_speed_avg.get("upload_speed") * 1024:
                        hashes.append(hash_string)
                        continue
                    else:
                        torrent_info.uploaded = prop.get('total_uploaded')
                        torrent_info.save()
            not_registered_msg = [
                'torrent not registered with this tracker',
            ]
            trackers = client.torrents_trackers(torrent_hash=hash_string)
            tracker_checked = False
            for tracker in trackers:
                if tracker.get('msg') in not_registered_msg:
                    hashes.append(hash_string)
                    tracker_checked = True
                    break
            if tracker_checked:
                continue
            # 完成人数超标删除
            torrent_num_complete = rules.get("num_complete")
            if torrent_num_complete and torrent_num_complete > 0:
                num_complete = prop.get('seeds_total')
                if num_complete > torrent_num_complete:
                    hashes.append(hash_string)
                    continue
            # 正在下载人数 低于设定值删除
            torrent_num_incomplete = rules.get("num_incomplete")
            if torrent_num_incomplete and torrent_num_incomplete > 0:
                num_incomplete = torrent.get('num_incomplete')
                if num_incomplete < torrent_num_incomplete:
                    hashes.append(hash_string)
                    continue
            # 无上传五下载超时删种
            if rules.get("timeout") and rules.get("timeout") > 0:
                last_activity = torrent.get('last_activity')
                if time.time() - last_activity > rules.get("timeout"):
                    hashes.append(hash_string)
                    continue
            # 进度与平均上传速度达标检测
            progress = torrent.get('progress')
            progress_check = rules.get("progress_check")
            if progress_check and len(progress_check) > 0:
                progress_checked = False
                for key, value in progress_check.items():
                    if progress >= float(key) and prop.get('up_speed_avg') < value * 1024:
                        hashes.append(hash_string)
                        progress_checked = True
                        break
                if progress_checked:
                    continue
            # 指定时间段内分享率不达标
            ratio_check = rules.get("ratio_check")
            ratio = prop.get('share_ratio')
            if rules.get("max_ratio") and ratio >= rules.get("max_ratio"):
                hashes.append(hash_string)
                continue
            if ratio_check and len(ratio_check) > 0:
                ratio_checked = False
                time_active = prop.get('time_elapsed')
                for key, value in ratio_check.items():
                    if time_active >= float(key) and ratio < value:
                        hashes.append(hash_string)
                        ratio_checked = True
                        break
                if ratio_checked:
                    continue

    if len(hashes) > 0:
        client.torrents_reannounce(torrent_hashes=hashes)
        # 单次最多删种数量
        num_delete = rules.get("num_delete")
        client.torrents_delete(torrent_hashes=hashes[:num_delete], delete_files=True)
    msg = f'{my_site.nickname}：本次运行删除种子{len(hashes)}个！' \
          f'当前有{len(torrent_infos) - len(hashes)}个种子正在运行'
    logger.info(msg)
    return msg


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
        ]
        trackers = client.torrents_trackers(torrent_hash=hash_string)
        tracker_checked = False
        for tracker in trackers:
            if tracker.get('msg') in not_registered_msg:
                hashes.append(hash_string)
                tracker_checked = True
                break
            if tracker.get('num_seeds') > 5:
                hashes.append(hash_string)
                tracker_checked = True
                break
        if tracker_checked:
            continue

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


def get_hashes(downloader_id):
    """返回下载器中所有种子的HASH列表"""
    client, downloader_category = get_downloader_instance(downloader_id)
    hashes = []
    if downloader_category == DownloaderCategory.qBittorrent:
        torrents = client.torrents_info()
        hashes = [torrent.get('hash') for torrent in torrents]
    if downloader_category == DownloaderCategory.Transmission:
        torrents = client.get_torrents()
        hashes = [torrent.hashString for torrent in torrents]
    return hashes
