import hashlib
import json
import logging
import time
from typing import List

import qbittorrentapi
import requests
import transmission_rpc
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.responses import codes_4xx

from auxiliary.base import DownloaderCategory
from download.schema import *
from monkey.schema import CommonMessage

# Create your views here.

logger = logging.getLogger('ptools')

router = Router(tags=['download'])


@router.get('/downloaders', response={200: List[DownloaderSchemaOut], codes_4xx: CommonMessage},
            description='下载器列表')
def get_downloaders(request):
    downloaders = Downloader.objects.all()
    if len(downloaders) <= 0:
        return 404, {'msg': '还没有下载器，快去添加吧 ~', 'code': -1}
    return downloaders


@router.get('/downloaders/{int:downloader_id}', response=DownloaderSchemaOut)
def get_downloader(request, downloader_id):
    return get_object_or_404(Downloader, id=downloader_id)


@router.post('/downloaders')
def add_downloader(request, downloader: DownloaderSchemaIn):
    return 'add'


@router.put('/downloaders/{int:downloader_id}')
def edit_downloader(request, downloader_id):
    return f'edit/{downloader_id}'


@router.delete('/downloaders/{int:downloader_id}')
def remove_downloader(request, downloader_id):
    count = Downloader.objects.filter(id=downloader_id).delete()
    return f'remove/{count}'


def get_downloader_instance(downloader_id):
    """根据id获取下载实例"""
    logger.info('当前下载器id：{}'.format(downloader_id))
    downloader = Downloader.objects.filter(id=downloader_id).first()
    if downloader.category == DownloaderCategory.qBittorrent:
        client = qbittorrentapi.Client(
            host=downloader.host,
            port=downloader.port,
            username=downloader.username,
            password=downloader.password,
            SIMPLE_RESPONSES=True
        )
    if downloader.category == DownloaderCategory.Transmission:
        client = transmission_rpc.Client(
            host=downloader.host, port=downloader.port,
            username=downloader.username, password=downloader.password
        )
    return client, downloader.category


@router.get('/categories/{downloader_id}',
            response={200: List[CategorySchema], codes_4xx: CommonMessage},
            description='获取下载器分类（QB）、常用文件夹（TR）')
def get_downloader_categories(request, downloader_id: int):
    client, category = get_downloader_instance(downloader_id)
    try:
        if category == DownloaderCategory.qBittorrent:
            client.auth_log_in()
            categories = [index for index, value in client.torrents_categories().items()]
            return categories
        if category == DownloaderCategory.Transmission:
            pass
    except Exception as e:
        logger.warning(e)
        # raise
        return 404, {'msg': f'下载器分类/下载路径获取失败: {e}', 'code': -1}


@router.post('/control/{downloader_id}', response=CommonMessage, description='操作种子')
def control_torrent(request, downloader_id: int, control_command: ControlTorrentCommandIn):
    ids = control_command.ids
    command = control_command.command
    delete_files = control_command.delete_files
    category = control_command.category
    enable = control_command.enable
    client, downloader_category = get_downloader_instance(downloader_id)
    try:
        if downloader_category == DownloaderCategory.qBittorrent:
            client.auth_log_in()
            # qb_client.torrents.resume()
            # 根据指令字符串定位函数
            command_exec = getattr(client.torrents, command)
            logger.info(command_exec)
            command_exec(
                torrent_hashes=ids.split(','),
                category=category,
                delete_files=delete_files,
                enable=enable, )
            # 延缓2秒等待操作生效
            time.sleep(2)
            return 200, {'msg': f'指令发送成功！', 'code': 0}
        if downloader_category == DownloaderCategory.Transmission:
            # return 200, {'msg': f'指令发送成功！', 'code': 0}
            return 501, {'msg': f'TR下载器控制尚未开发完毕！', 'code': -1}
    except Exception as e:
        logger.warning(e)
        return 500, {'msg': f'执行指令失败： {e}', 'code': -1}


def get_hashes():
    """返回下载器中所有种子的HASH列表"""
    return []


def get_torrents_hash_from_server():
    """将本地HASH列表提交至服务器，请求返回可辅种数据"""
    # 如果为IYUU支持的站点，先向IYUU请求数据
    # 否则向ptools请求数据
    # 将本地hash列表与返回数据进行去重，生成种子链接列表
    return []


def push_torrents_to_downloader():
    """将辅种数据推送至下载器"""
    # 暂停模式推送至下载器（包含参数，下载链接，Cookie，分类或者下载路径）
    # 开始校验
    # 验证校验结果，不为百分百的，暂停任务
    return []


def get_torrents_hash_from_iyuu():
    # hash_list = get_hashes()
    hash_list = ['ff06699c8bf1003f46ac07621b967d16e7baac78']
    hash_list_str = json.dumps(hash_list)
    hash_list_sha1 = hashlib.sha1(hash_list_str.encode('utf8'))
    url = 'http://api.iyuu.cn/index.php?s=App.Api.Infohash'
    data = {
        # IYUU token
        'sign': 'IYUU10227T6942484114699c63a6df9bc30f3c81f1bd1cd9b4',
        # 当前时间戳
        'timestamp': int(time.time()),
        # 客户端版本
        'version': '2.0.0',
        # hash列表
        'hash': hash_list_str,
        # hash列表sha1
        'sha1': hash_list_sha1.hexdigest()

    }
    res = requests.post(
        url=url,
        data=data
    )
    print(res.json())
    return res.json()


if __name__ == '__main__':
    get_torrents_hash_from_iyuu()
