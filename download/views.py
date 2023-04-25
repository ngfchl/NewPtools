import hashlib
import json
import logging
import time
import traceback

import qbittorrentapi
import requests
import transmission_rpc
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.responses import codes_4xx

from auxiliary.base import DownloaderCategory
from download.schema import *
from monkey.schema import CommonMessage
from toolbox.schema import CommonResponse

# Create your views here.

logger = logging.getLogger('ptools')

router = Router(tags=['download'])


@router.get('/downloaders', response=CommonResponse[List[DownloaderSchemaOut]],
            description='下载器列表')
def get_downloaders(request):
    downloaders = Downloader.objects.all()
    return CommonResponse.success(data=list(downloaders))


@router.get('/downloader', response=CommonResponse[DownloaderSchemaIn])
def get_downloader(request, downloader_id: int):
    downloader = get_object_or_404(Downloader, id=downloader_id)
    return CommonResponse.success(data=downloader)


@router.post('/downloader', response=CommonResponse[DownloaderSchemaIn])
def add_downloader(request, downloader: DownloaderSchemaIn):
    downloader = Downloader.objects.create(downloader.dict())
    return CommonResponse.success(data=downloader)


@router.put('/downloader', response=CommonResponse[DownloaderSchemaIn])
def edit_downloader(request, downloader: DownloaderSchemaIn):
    new_downloader = Downloader.objects.update_or_create(defaults=downloader.dict(), id=downloader.id)
    return CommonResponse.success(data=new_downloader[0])


@router.delete('/downloader', response=CommonResponse)
def remove_downloader(request, downloader_id: int):
    try:
        count = Downloader.objects.filter(id=downloader_id).delete()
        if count > 0:
            return CommonResponse.success(msg='删除成功！')
        return CommonResponse.error(msg='删除失败！')
    except Exception as e:
        logger.error(e)
        return CommonResponse.error(msg='删除失败！')


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


@router.get('/downloaders/speed', response=CommonResponse[List[TransferSchemaOut]], description='实时上传下载')
def get_downloader_speed(request):
    downloader_list = Downloader.objects.filter(enable=True).all()
    info_list = []
    for downloader in downloader_list:
        try:
            client, _ = get_downloader_instance(downloader.id)
            if downloader.category == DownloaderCategory.qBittorrent:
                # x = {'connection_status': 'connected', 'dht_nodes': 0, 'dl_info_data': 2577571007646,
                #      'dl_info_speed': 3447895, 'dl_rate_limit': 41943040, 'up_info_data': 307134686158,
                #      'up_info_speed': 4208516, 'up_rate_limit': 0, 'category': 'Qb', 'name': 'home-qb'}
                info = client.transfer.info
                info.update({
                    'category': downloader.category,
                    'name': downloader.name,
                    'connection_status': True if info.get('connection_status') == 'connected' else False
                })
            elif downloader.category == DownloaderCategory.Transmission:
                base_info = client.session_stats().fields
                """
                info = {'activeTorrentCount': 570,
                        'cumulative-stats': {
                            'downloadedBytes': 1627151110618,
                            'filesAdded': 1765384,
                            'secondsActive': 13861806,
                            'sessionCount': 36,
                            'uploadedBytes': 10230987475236
                        },
                        'current-stats': {
                            'downloadedBytes': 0,
                            'filesAdded': 0,
                            'secondsActive': 80761,
                            'sessionCount': 1,
                            'uploadedBytes': 27312187754
                        },
                        'downloadSpeed': 0,
                        'pausedTorrentCount': 0,
                        'torrentCount': 570,
                        'uploadSpeed': 0
                        }
                """
                info = {
                    'connection_status': True,
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
                info = {
                    'category': downloader.category,
                    'name': downloader.name,
                    'connection_status': False,
                    'dl_info_data': 0,
                    'dl_info_speed': 0,
                    'up_info_data': 0,
                    'up_info_speed': 0,
                }
        except Exception as e:
            info = {
                'category': downloader.category,
                'name': downloader.name,
                'connection_status': False,
                'dl_info_data': 0,
                'dl_info_speed': 0,
                'up_info_data': 0,
                'up_info_speed': 0,
            }
        info_list.append(info)
    # logger.info(info_list)
    return CommonResponse.success(data=info_list)


@router.get('/downloaders/downloading', response=CommonResponse, description='当前种子')
def get_downloading(request, downloader_id: int):
    logger.info('当前下载器id：{}'.format(downloader_id))
    qb_client, category = get_downloader_instance(downloader_id)
    try:
        if category == DownloaderCategory.qBittorrent:
            # qb_client.auth_log_in()
            # transfer = qb_client.transfer_info()
            # torrents = qb_client.torrents_info()
            main_data = qb_client.sync_maindata()
            del main_data['trackers']
            del main_data['tags']
            del main_data['rid']
            del main_data['full_update']
            torrent_list = main_data.get('torrents')
            torrents = []
            for index, torrent in torrent_list.items():
                torrent['hash'] = index
                get_torrent_trackers(qb_client, torrent)
                torrents.append(torrent)
            logger.info('当前下载器共有种子：{}个'.format(len(torrents)))
            main_data['torrents'] = torrents
            main_data['categories'] = list(main_data['categories'].values())

            return CommonResponse.success(data=main_data)
        else:
            return CommonResponse.error(msg='尚未支持Tr下载器')
    except Exception as e:
        logger.error(traceback.format_exc(limit=3))
        return JsonResponse(CommonResponse.error(
            msg='连接下载器出错咯！'
        ).to_dict(), safe=False)


@router.get('/downloaders/torrent/props', response=CommonResponse, description='当前种子属性')
def get_torrent_properties_api(request, downloader_id: int, torrent_hash: str):
    qb_client, category = get_downloader_instance(downloader_id)
    try:
        # qb_client.auth_log_in()
        torrent = qb_client.torrents.info(torrent_hashes=torrent_hash)
        properties = qb_client.torrents_properties(torrent_hash=torrent_hash)
        torrent[0].update(properties)
        get_torrent_trackers(qb_client, torrent[0])
        return CommonResponse.success(data=torrent[0])
    except Exception as e:
        logger.error(traceback.format_exc(limit=3))
        return JsonResponse(CommonResponse.error(
            msg='连接下载器出错咯！'
        ).to_dict(), safe=False)


def get_torrent_properties(client, torrent_hash):
    properties = client.torrents_properties(torrent_hash=torrent_hash)
    if properties.get('peers') > 0:
        properties.update(
            {'peerList': list(client.sync_torrent_peers(torrent_hash=torrent_hash).get('peers').values())})
    return properties


def get_torrent_trackers(client, torrent):
    trackers = client.torrents_trackers(torrent_hash=torrent.get('hash'))
    trackers = [tracker for tracker in trackers if tracker['url'] == torrent['tracker']]
    torrent['trackers'] = []
    torrent['trackers'].append({'status': 1, 'url': torrent.get('tracker')}) if len(trackers) <= 0 else torrent[
        'trackers'].extend(trackers)


@router.get('/categories/{downloader_id}',
            response={200: List[CategorySchema], codes_4xx: CommonMessage},
            description='获取下载器分类（QB）、常用文件夹（TR）')
def get_downloader_categories(request, downloader_id: int):
    client, category = get_downloader_instance(downloader_id)
    try:
        if category == DownloaderCategory.qBittorrent:
            # client.auth_log_in()
            categories = [index for index, value in client.torrents_categories().items()]
            return categories
        if category == DownloaderCategory.Transmission:
            pass
    except Exception as e:
        logger.warning(e)
        # raise
        return 404, {'msg': f'下载器分类/下载路径获取失败: {e}', 'code': -1}


@router.post('/control', response=CommonResponse, description='操作种子')
def control_torrent(request, control_command: ControlTorrentCommandIn):
    # if control_command.downloader_id > 0:
    #     return CommonResponse.success(msg=str(control_command.dict()))
    ids = control_command.ids
    command = control_command.command
    delete_files = control_command.delete_files
    category = control_command.category
    enable = control_command.enable
    client, downloader_category = get_downloader_instance(control_command.downloader_id)
    try:
        if downloader_category == DownloaderCategory.qBittorrent:
            # client.auth_log_in()
            # qb_client.torrents.resume()
            # 根据指令字符串定位函数
            command_exec = getattr(client.torrents, command)
            logger.info(command_exec)
            command_exec(
                torrent_hashes=ids,
                category=category,
                delete_files=delete_files,
                enable=enable, )
            # 延缓2秒等待操作生效
            time.sleep(1.5)
            return CommonResponse.success(msg=f'指令发送成功!')
        if downloader_category == DownloaderCategory.Transmission:
            # return 200, {'msg': f'指令发送成功！', 'code': 0}
            return CommonResponse.error(msg=f'TR下载器控制尚未开发完毕!')
    except Exception as e:
        logger.warning(e)
        return CommonResponse.error(msg=f'执行指令失败!')


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
    logger.info(res.json())
    return res.json()


if __name__ == '__main__':
    get_torrents_hash_from_iyuu()
