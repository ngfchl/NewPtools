import logging
import time
from typing import List

import qbittorrentapi
import transmission_rpc
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
