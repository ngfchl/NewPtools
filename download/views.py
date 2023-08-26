import logging
import time
import traceback
import urllib.parse

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ninja import Router

import toolbox.views as toolbox
from auxiliary.base import DownloaderCategory
from download.schema import *
from toolbox.schema import CommonResponse
from website.models import WebSite

# Create your views here.

logger = logging.getLogger('ptools')

router = Router(tags=['download'])


@router.get('/downloaders', response=CommonResponse[List[DownloaderSchemaOut]],
            description='下载器列表')
def get_downloaders(request):
    downloaders = Downloader.objects.all()
    return CommonResponse.success(data=list(downloaders))


@router.get('/downloader/test', response=CommonResponse)
def test_connect(request, downloader_id):
    try:
        downloader = Downloader.objects.filter(id=downloader_id).first()
        client, category = toolbox.get_downloader_instance(downloader_id)
        msg = f'下载器：{downloader.name} 连接成功！'
        logger.info(msg=msg)
        return CommonResponse.success(msg=msg)
    except Exception as e:
        msg = f"下载器：{downloader_id} 连接失败！"
        logger.error(msg)
        return CommonResponse.error(msg=msg)


@router.get('/downloader', response=CommonResponse[DownloaderSchemaIn])
def get_downloader(request, downloader_id: int):
    downloader = get_object_or_404(Downloader, id=downloader_id)
    return CommonResponse.success(data=downloader)


@router.post('/downloader', response=CommonResponse[DownloaderSchemaIn])
def add_downloader(request, downloader: DownloaderSchemaIn):
    downloader_dict = downloader.dict()
    del downloader_dict['id']
    downloader = Downloader.objects.create(**downloader_dict)
    return CommonResponse.success(data=downloader)


@router.put('/downloader', response=CommonResponse[Optional[DownloaderSchemaIn]])
def edit_downloader(request, downloader: DownloaderSchemaIn):
    try:
        new_downloader = Downloader.objects.update_or_create(defaults=downloader.dict(), id=downloader.id)
        return CommonResponse.success(data=new_downloader[0], msg=f'{new_downloader[0].name} 修改成功！')
    except Exception as e:
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=f'{downloader.name} 修改出错啦！')


@router.delete('/downloader', response=CommonResponse)
def remove_downloader(request, downloader_id: int):
    try:
        count = Downloader.objects.filter(id=downloader_id).delete()
        if count[0] > 0:
            return CommonResponse.success(msg='删除成功！')
        return CommonResponse.error(msg='删除失败！')
    except Exception as e:
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg='删除失败！')


@router.get('/downloaders/speed', response=CommonResponse[Union[List[TransferSchemaOut], TransferSchemaOut, None]],
            description='实时上传下载')
def get_downloader_speed_list(request, downloader_id: Optional[int] = 0):
    if downloader_id == 0:
        downloader_list = Downloader.objects.filter(enable=True).all()
        info_list = []
        for downloader in downloader_list:
            info = toolbox.get_downloader_speed(downloader)
            info_list.append(info)
        # logger.info(info_list)
        return CommonResponse.success(data=info_list)
    else:
        downloader = Downloader.objects.filter(pk=downloader_id, enable=True).first()
        if not downloader:
            return CommonResponse.error(msg='出错啦！')
        return CommonResponse.success(data=toolbox.get_downloader_speed(downloader))


@router.get('/downloaders/downloading', response=CommonResponse, description='当前种子')
def get_downloading(request, downloader_id: int, prop: bool = False, torrent_hashes: str = ''):
    if prop:
        website_list = WebSite.objects.all()
    logger.info('当前下载器id：{}'.format(downloader_id))
    client, category = toolbox.get_downloader_instance(downloader_id)
    try:
        if category == DownloaderCategory.qBittorrent:
            torrent_list = client.torrents_info(torrent_hashes=torrent_hashes)
            torrents = []
            for torrent in torrent_list:
                if prop:
                    url = torrent.get('tracker')
                    hostname = urllib.parse.urlparse(url).hostname
                    torrent['host'] = hostname
                    trackers = client.torrents_trackers(torrent_hash=torrent.get('hash'))
                    trackers = [tracker for tracker in trackers if torrent.get('tracker') and
                                tracker.get('status') > 0 and tracker.get('url') == url]
                    torrent['trackers'] = trackers if len(trackers) > 0 else [{
                        'status': 1,
                    }]
                torrents.append(torrent)
            logger.info('当前获取种子信息：{}条'.format(len(torrents)))
            return CommonResponse.success(data=torrents)
        else:
            if len(torrent_hashes) > 0:
                torrent_hashes = torrent_hashes.split('|')
                torrents = client.get_torrents(ids=torrent_hashes)
            else:
                torrents = client.get_torrents()
            torrent_list = []
            for torrent in torrents:
                torrent = torrent.fields
                if prop:
                    url = torrent.get('trackers')[0].get('announce')
                    hostname = urllib.parse.urlparse(url).hostname
                    torrent['host'] = hostname
                    file_status = []
                    for file, state in zip(torrent['files'], torrent['fileStats']):
                        file.update(state)
                        file_status.append(file)
                    torrent['fileStats'] = file_status
                torrent['hash'] = torrent.get('hashString')
                del torrent['files']
                torrent_list.append(torrent)
            # hosts = set([torrent.get('host') for torrent in torrents])
            # print(hosts)
            return CommonResponse.success(data=torrent_list)
    except Exception as e:
        logger.error(traceback.format_exc(limit=3))
        return JsonResponse(CommonResponse.error(
            msg='连接下载器出错咯！'
        ).to_dict(), safe=False)


@router.get('/downloaders/torrent/props', response=CommonResponse, description='当前种子属性')
def get_torrent_properties_api(request, downloader_id: int, torrent_hash: str):
    client, category = toolbox.get_downloader_instance(downloader_id)
    try:
        if category == DownloaderCategory.qBittorrent:
            torrent_list = client.torrents.info(torrent_hashes=torrent_hash)
            torrent = torrent_list[0]
            properties = client.torrents_properties(torrent_hash=torrent_hash)
            if properties.get('peers') > 0:
                properties.update(
                    {'peerList': list(client.sync_torrent_peers(torrent_hash=torrent_hash).get('peers').values())})
            trackers = client.torrents_trackers(torrent_hash=torrent.get('hash'))
            trackers = [tracker for tracker in trackers if tracker['url'] == torrent['tracker']]
            torrent['trackers'] = []
            torrent['trackers'].append({'status': 1, 'url': torrent.get('tracker')}) if len(trackers) <= 0 else torrent[
                'trackers'].extend(trackers)
            files = client.torrents_files(torrent_hash=torrent_hash)
            torrent.update(properties)
            torrent['files'] = client.torrents_files(torrent_hash=torrent_hash)
            return CommonResponse.success(data=torrent)
        else:
            torrent = client.get_torrent(torrent_id=torrent_hash)
            torrent = torrent.fields
            torrent['hash'] = torrent.get('hashString')
            file_status = []
            for file, state in zip(torrent['files'], torrent['fileStats']):
                file.update(state)
                file_status.append(file)
            del torrent['files']
            torrent['files'] = file_status
            return CommonResponse.success(data=torrent)
    except Exception as e:
        logger.error(traceback.format_exc(limit=3))
        return JsonResponse(CommonResponse.error(
            msg='获取种子详情出错咯！'
        ).to_dict(), safe=False)


@router.get('downloaders/categories',
            response=CommonResponse[List[Optional[CategorySchema]]],
            description='获取下载器分类（QB）、常用文件夹（TR）')
def get_downloader_categories(request, downloader_id: int):
    client, category = toolbox.get_downloader_instance(downloader_id)
    try:
        if category == DownloaderCategory.qBittorrent:
            # client.auth_log_in()
            categories = [category for category in client.torrents_categories().values()]
            return CommonResponse.success(data=categories)
        if category == DownloaderCategory.Transmission:
            torrents = client.get_torrents(arguments=['id', 'name', 'downloadDir'])
            save_paths = set()
            for torrent in torrents:
                save_paths.add(torrent.fields.get('downloadDir'))
            categories = [{
                'name': download_dir.rstrip('/').split('/')[-1],
                'savePath': download_dir
            } for download_dir in list(save_paths)]
            return CommonResponse.success(data=categories)
    except Exception as e:
        logger.warning(e)
        # raise
        return {'msg': f'下载器分类/下载路径获取失败: {e}', 'code': -1}


@router.post('/control', response=CommonResponse, description='操作种子')
def control_torrent(request, control_command: ControlTorrentCommandIn):
    # if control_command.downloader_id > 0:
    #     return CommonResponse.success(msg=str(control_command.dict()))
    ids = control_command.ids
    command = control_command.command
    delete_files = control_command.delete_files
    category = control_command.category
    enable = control_command.enable
    client, downloader_category = toolbox.get_downloader_instance(control_command.downloader_id)
    try:
        if downloader_category == DownloaderCategory.qBittorrent:
            # client.auth_log_in()
            # qb_client.torrents.resume()
            # 根据指令字符串定位函数
            if command == 'removeCategories':
                client.torrents_removeCategories('')
            else:
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
            if command == 'delete':
                client.remove_torrent(ids=ids, delete_data=delete_files)
            elif command == 'set_category':
                client.move_torrent_data(ids=ids, location=category)
            else:
                command_exec = getattr(client, command)
                command_exec(ids=ids)
            return CommonResponse.success(msg=f'指令发送成功！')
    except Exception as e:
        logger.warning(traceback.format_exc(3))
        return CommonResponse.error(msg=f'执行指令失败!')


@router.post('/add_torrent', response=CommonResponse, description='添加种子')
def add_torrent(request, new_torrent: AddTorrentCommandIn):
    torrent = new_torrent.new_torrent
    try:
        client, downloader_category = toolbox.get_downloader_instance(new_torrent.downloader_id)
        return toolbox.push_torrents_to_downloader(
            client, downloader_category,
            urls=torrent.urls,
            category=torrent.category,
            is_skip_checking=torrent.is_skip_checking,
            is_paused=torrent.is_paused,
            upload_limit=torrent.upload_limit,
            download_limit=torrent.download_limit,
            use_auto_torrent_management=torrent.use_auto_torrent_management,
            cookie=torrent.cookie
        )
    except Exception as e:
        logger.info(traceback.format_exc(3))
        return CommonResponse.error(msg='添加失败！')


@router.get('/brush_remove', response=CommonResponse, description='删种脚本')
def brush_remove_torrent(request, downloader_id: int):
    client, downloader_category = toolbox.get_downloader_instance(downloader_id)
    if downloader_category == DownloaderCategory.Transmission:
        return CommonResponse.error(msg='不支持Transmission!')
    hashes = toolbox.torrents_filter_by_percent_completed_rule(client, num_complete_percent=0.5, downloaded_percent=0.9)
    client.torrents_delete(delete_files=True, torrent_hashes=hashes)
    return CommonResponse.success(msg=f'指令发送成功!删除{len(hashes)}个种子！')


@router.get('/repeat_torrent', response=CommonResponse, description='获取种子辅种信息')
def repeat_torrent(request, torrent_hashes: str):
    res = toolbox.parse_hashes_from_iyuu(torrent_hashes)
    return res
