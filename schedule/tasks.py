from __future__ import absolute_import, unicode_literals

import gc
import hashlib
import logging
import os
import subprocess
import time
import traceback
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool
from typing import List

import requests
import toml
from celery.app import shared_task
from django.core.cache import cache
from django.db.models import Q
from lxml import etree

from auxiliary.base import MessageTemplate
from auxiliary.celery import BaseTask
from my_site.models import MySite, TorrentInfo
from spider.views import PtSpider, toolbox
from toolbox.schema import CommonResponse
from website.models import WebSite

# 引入日志
logger = logging.getLogger('ptools')
# 引入线程池
pool = ThreadPool(8)
pt_spider = PtSpider()


# @boost('do_sign_in', broker_kind=BrokerEnum.REDIS_STREAM)
@shared_task(bind=True, base=BaseTask)
def auto_sign_in(self, site_list: List[int] = []):
    """执行签到"""
    start = time.time()
    logger.info('开始执行签到任务')
    toolbox.send_text(title='通知：正在签到', message=f'开始执行签到任务，当前时间：{datetime.fromtimestamp(start)}')
    logger.info('筛选需要签到的站点')
    message_list = []
    sign_list = MySite.objects.filter(
        sign_in=True
    ) if len(site_list) == 0 else MySite.objects.filter(sign_in=True, id__in=site_list)
    # chatgpt 优化的代码：
    queryset = [
        my_site for my_site in sign_list
        if my_site.cookie and WebSite.objects.get(id=my_site.site).func_sign_in and
           my_site.signin_set.filter(created_at__date__gte=datetime.today(), sign_in_today=True).count() == 0 and
           (datetime.now().hour >= 9 or WebSite.objects.get(id=my_site.site).url not in ['https://u2.dmhy.org/'])
    ]
    """
    # 获取工具支持且本人开启签到的所有站点
    websites = WebSite.objects.all()
    sign_list = MySite.objects.filter(
        sign_in=True
    ) if len(site_list) == 0 else MySite.objects.filter(sign_in=True, id__in=site_list)
    # 获取已配置Cookie 且站点支持签到，今日无签到数据的站点列表
    queryset = [my_site for my_site in sign_list if my_site.cookie and websites.get(id=my_site.site).func_sign_in
                and my_site.signin_set.filter(created_at__date__gte=datetime.today(), sign_in_today=True).count() <= 0]
    if datetime.now().hour < 9 and len(queryset) > 0:
        print(queryset)
        print(type(queryset))
        # U2/52PT 每天九点前不签到
        queryset = [my_site for my_site in queryset if WebSite.objects.get(id=my_site.site).url not in [
            'https://u2.dmhy.org/',
            # 'https://52pt.site/'
        ]]
    """
    message = '站点：`U2` 早上九点之前不执行签到任务哦！ \n\n'
    logger.info(message)
    message_list.append(message)
    if len(queryset) <= 0:
        message_list = ['已全部签到或无需签到！ \n\n']
        logger.info(message_list)
        toolbox.send_text(title='通知：自动签到', message='\n'.join(message_list))
        return message_list
    results = pool.map(pt_spider.sign_in, queryset)
    logger.info('执行签到任务')
    success_message = []
    failed_message = []
    for my_site, result in zip(queryset, results):
        logger.info(f'自动签到：{my_site}, {result}')
        if result.code == 0:
            msg = f'✅ {my_site.nickname} 签到成功！{result.msg} \n\n'
            logger.info(msg)
            success_message.append(msg)
        else:
            message = f'🆘 {my_site.nickname}签到失败：{result.msg} \n\n'
            failed_message.append(message)
            logger.error(message)
        # message_list.append(f'{my_site.nickname}: {result.msg}')
    end = time.time()
    message = f'当前时间：{datetime.fromtimestamp(end)},' \
              f'本次签到任务执行完毕，共有{len(queryset)}站点需要签到，成功签到{len(success_message)}个站点，' \
              f'失败{len(failed_message)}个站点，耗费时间：{round(end - start, 2)} \n'
    message_list.append(message)
    message_list.extend(failed_message)
    message_list.append('*' * 20)
    # message_list.extend(success_message)
    logger.info(message)
    logger.info(len(message_list))
    toolbox.send_text(title='通知：自动签到', message='\n'.join(message_list))
    toolbox.send_text(title='通知：签到成功', message='\n'.join(success_message))
    # 释放内存
    gc.collect()
    return message_list


@shared_task(bind=True, base=BaseTask)
def auto_get_status(self, site_list: List[int] = []):
    """
    更新个人数据
    """
    start = time.time()
    message_list = ['# 更新个人数据  \n\n']
    failed_message = []
    success_message = []
    websites = WebSite.objects.all()
    queryset = MySite.objects.filter(
        get_info=True
    ) if len(site_list) == 0 else MySite.objects.filter(get_info=True, id__in=site_list)
    site_list = [my_site for my_site in queryset if websites.get(id=my_site.site).func_get_userinfo]
    results = pool.map(pt_spider.send_status_request, site_list)
    message_template = MessageTemplate.status_message_template
    for my_site, result in zip(site_list, results):
        if result.code == 0:
            # res = pt_spider.parse_status_html(my_site, result.data)
            logger.info('自动更新个人数据: {}, {}'.format(my_site.nickname, result))
            # if res.code == 0:
            status = result.data
            message = message_template.format(
                my_site.nickname,
                status.my_level,
                status.my_bonus,
                status.bonus_hour,
                status.my_score,
                status.ratio,
                toolbox.FileSizeConvert.parse_2_file_size(status.seed_volume),
                toolbox.FileSizeConvert.parse_2_file_size(status.uploaded),
                toolbox.FileSizeConvert.parse_2_file_size(status.downloaded),
                status.seed,
                status.leech,
                status.invitation,
                status.my_hr,
            )
            logger.info(message)
            # toolbox.send_text(title='通知：个人数据更新', message=my_site.nickname + ' 信息更新成功！' + message)
            success_message.append(f'✅ {my_site.nickname} 信息更新成功！{message}\n\n')
        else:
            print(result)
            message = f'🆘 {my_site.nickname} 信息更新失败！原因：{result.msg}'
            logger.warning(message)
            failed_message.append(f'{message} \n\n')
            # toolbox.send_text(title='通知：个人数据更新', message=f'{my_site.nickname} 信息更新失败！原因：{message}')
    # 发送今日数据
    total_upload, total_download, increase_info_list = toolbox.today_data()
    increase_list = []
    for increase_info in increase_info_list:
        info = f'\n\n- ♻️ 站点：{increase_info.get("name")}'
        if increase_info.get("uploaded") > 0:
            info += f'\n\t\t⬆ {toolbox.FileSizeConvert.parse_2_file_size(increase_info.get("uploaded"))}'
        if increase_info.get("downloaded") > 0:
            info += f'\n\t\t⬇ {toolbox.FileSizeConvert.parse_2_file_size(increase_info.get("downloaded"))}'
        increase_list.append(info)
    incremental = f'⬆ 总上传：{toolbox.FileSizeConvert.parse_2_file_size(total_upload)}\n' \
                  f'⬇ 总下载：{toolbox.FileSizeConvert.parse_2_file_size(total_download)}\n' \
                  f'✔ 说明: 数据均相较于本站今日之前最近的一条数据，可能并非昨日\n' \
                  f'⚛ 数据列表：{"".join(increase_list)}'
    logger.info(incremental)
    toolbox.send_text(title='通知：今日数据', message=incremental)
    end = time.time()
    consuming = f'自动更新个人数据 任务运行成功！' \
                f'共计成功 {len(success_message)} 个站点，失败 {len(failed_message)} 个站点，' \
                f'耗时：{round(end - start, 2)} 完成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}  \n'
    message_list.append(consuming)
    logger.info(message_list)
    message_list.extend(failed_message)
    message_list.append('*' * 20)
    # message_list.extend(success_message)
    toolbox.send_text(title='通知：更新个人数据', message='\n'.join(message_list))
    toolbox.send_text(title='通知：更新个人数据-成功', message='\n'.join(success_message))
    # 释放内存
    gc.collect()
    return message_list


@shared_task(bind=True, base=BaseTask, autoretry_for=(Exception,), )
def auto_get_torrents(self, site_list: List[int] = []):
    """
    拉取最新种子
    """
    start = time.time()
    message_list = ['# 拉取免费种子  \n\n']
    message_success = []
    message_failed = []
    websites = WebSite.objects.all()
    queryset = MySite.objects.filter(id__in=site_list) if len(site_list) > 0 else MySite.objects.all()
    site_list = [my_site for my_site in queryset if websites.get(id=my_site.site).func_brush_free]
    results = pool.map(pt_spider.send_torrent_info_request, site_list)
    for my_site, result in zip(site_list, results):
        logger.info('获取种子：{}{}'.format(my_site.nickname, result))
        # print(result is tuple[int])
        if result.code == 0:
            res = pt_spider.get_torrent_info_list(my_site, result.data)
            # 通知推送
            if res.code == 0:
                message = f'> ✅ {my_site.nickname}种子抓取成功！ {res.msg}  \n\n'
                message_success.append(message)
                logger.info(message)
            else:
                message = f'> 🆘 {my_site.nickname} 抓取种子信息失败！原因：{res.msg}  \n'
                message_failed.append(message)
                logger.error(message)
        else:
            # toolbox.send_text(my_site.nickname + ' 抓取种子信息失败！原因：' + result[0])
            message = f'> 🆘 {my_site.nickname} 抓取种子信息失败！原因：{result.msg}  \n'
            logger.error(message)
            message_failed.append(message)
    end = time.time()
    consuming = f'> ♻️ 拉取最新种子 任务运行成功！共有{len(site_list)}个站点需要执行，执行成功{len(message_success)}个，失败{len(message_failed)}个。' \
                f'本次任务耗时：{end - start} 当前时间：{time.strftime("%Y-%m-%d %H:%M:%S")}  \n'
    message_list.append(consuming)
    message_list.extend(message_failed)
    logger.info(consuming)
    toolbox.send_text(title='通知：拉取最新种子', message=''.join(message_list))
    if len(message_success) > 0:
        toolbox.send_text(title='通知：拉取最新种子-成功', message=''.join(message_success))
    # 释放内存
    gc.collect()


@shared_task(bind=True, base=BaseTask)
def auto_calc_torrent_pieces_hash(self, ):
    """
    计算种子块HASH
    """
    start = time.time()
    torrent_info_list = TorrentInfo.objects.filter(downloader__isnull=False).all()
    website_list = WebSite.objects.all()
    count = 0
    for torrent_info in torrent_info_list:
        logger.info('种子名称：{}'.format(torrent_info.name))
        try:
            client, _ = toolbox.get_downloader_instance(torrent_info.downloader_id)
            if not torrent_info.hash_string:
                # 种子信息未填写hash的，组装分类信息，到下载器查询种子信息
                site = website_list.get(id=torrent_info.site.site)
                category = f'{site.nickname}{torrent_info.tid}'
                torrents = client.torrents_info(category=category)
            else:
                # 以后hash的直接查询
                torrents = client.torrents_info(torrent_hashes=torrent_info.hash_string)
            if len(torrents) == 1:
                # 保存种子hash
                hash_string = torrents[0].hash_string
                torrent_info.hash_string = hash_string
                # 获取种子块HASH列表，并生成种子块HASH列表字符串的sha1值，保存
                pieces_hash_list = client.torrents_piece_hashes(torrent_hash=hash_string)
                pieces_hash_string = str(pieces_hash_list).replace(' ', '')
                torrent_info.pieces_hash = hashlib.sha1(pieces_hash_string.encode()).hexdigest()
                # 获取文件列表，并生成文件列表字符串的sha1值，保存
                file_list = client.torrents_files(torrent_hash=hash_string)
                file_list_hash_string = str(file_list).replace(' ', '')
                torrent_info.filelist = hashlib.sha1(file_list_hash_string.encode()).hexdigest()
            torrent_info.state = True
            torrent_info.save()
            count += 1
        except Exception as e:
            logging.error(traceback.format_exc(3))
            continue
    end = time.time()
    message = f'> 计算种子Pieces的HASH值 任务运行成功！共成功处理种子{count}个，耗时：{end - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")}'
    toolbox.send_text(title='通知：计算种子HASH', message=message)
    # 释放内存
    gc.collect()


@shared_task(bind=True, base=BaseTask)
def auto_get_rss(self, site_list: str):
    start = time.time()
    site_list = site_list.split('|')
    my_site_list = MySite.objects.filter(id__in=site_list, brush_rss=True).all()
    websites = WebSite.objects.filter(func_brush_rss=True).all()
    message_list = []
    message_failed = []
    message_success = []
    for my_site in my_site_list:
        try:
            website = websites.get(id=my_site.site)
            if not website:
                # 聊胜于无？
                logger.warning(f'{my_site.nickname} 暂不支持RSS刷流！')
                continue
            torrents = toolbox.parse_rss(my_site.rss)
            updated = 0
            created = 0
            hash_list = []
            urls = []
            for torrent in torrents:
                tid = torrent.get('tid')
                # 组装种子详情页URL 解析详情页信息
                # res_detail = pt_spider.get_torrent_detail(my_site, f'{website.url}{website.page_detail.format(tid)}')
                # 如果无报错，将信息合并到torrent
                # if res_detail.code == 0:
                #     torrent.update(res_detail.data)
                res = TorrentInfo.objects.update_or_create(site=my_site, tid=tid, defaults=torrent, )
                if res[1]:
                    urls.append(f'{website.url}{website.page_download.format(tid)}')
                    hash_list.append(res[0].hash_string)
                    created += 1
                else:
                    updated += 1
                # logger.info(res)
            msg = f'{my_site.nickname} 新增种子：{created} 个，更新种子：{updated}个！'
            logger.info(msg)
            message_success.append(msg)
            if my_site.downloader:
                downloader = my_site.downloader
                res = toolbox.push_torrents_to_downloader(
                    downloader_id=my_site.downloader.id,
                    urls=urls,
                    cookie=my_site.cookie,
                    is_paused=downloader.package_files,
                )
                logging.info(f'本次任务推送状态：{res.msg}')
                cache_hash_list = cache.get(f'brush-{my_site.id}-{my_site.nickname}')
                if not cache_hash_list or len(cache_hash_list) <= 0:
                    cache_hash_list = hash_list
                else:
                    cache_hash_list.extend(hash_list)
                cache.set(f'brush-{my_site.id}-{my_site.nickname}', cache_hash_list, 24 * 60 * 60)
                message = f'> RSS 任务运行成功！耗时：{time.time() - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")} \n'
                logging.info(f'下载器拆包状态：{downloader.package_files}')
                if downloader.package_files:
                    package_start = time.time()
                    client, _ = toolbox.get_downloader_instance(downloader.id)
                    time.sleep(25)
                    for hash_string in hash_list:
                        try:
                            toolbox.package_files(client=client, hash_string=hash_string)
                        except Exception as e:
                            logger.error(traceback.format_exc(3))
                            continue
                    toolbox.send_text(
                        title='拆包',
                        message=f'拆包任务执行结束！耗时：{time.time() - package_start}\n{time.strftime("%Y-%m-%d %H:%M:%S")} \n')
                    # package_files = {
                    #     'time': time.strftime("%Y-%m-%d %H:%M:%S"),
                    #     'site': my_site.nickname,
                    #     'downloader_id': downloader.id,
                    #     'hash_list': hash_list
                    # }
                    # # 从缓存获取需要拆包的任务参数列表
                    # cache_package_files_list = cache.get(f'cache_package_files_list')
                    # if not cache_package_files_list or len(cache_package_files_list) <= 0:
                    #     cache_package_files_list = [package_files]
                    # else:
                    #     # 如果列表存在就讲本次生成的参数添加到列表末尾
                    #     cache_package_files_list.append(package_files)
                    # # 更新参数列表
                    # cache.set(f'cache_package_files_list', cache_package_files_list, 60 * 60 * 24)
        except Exception as e:
            logger.error(traceback.format_exc(3))
            msg = f'{my_site.nickname} RSS获取或解析失败'
            logger.error(msg)
            message_failed.append(msg)
            continue
    end = time.time()
    message = f'> RSS + 拆包 任务运行成功！耗时：{end - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")} \n'
    message_list.append(message)
    message_list.extend(message_failed)
    message_list.extend(message_success)
    msg = '\n - '.join(message_list)
    toolbox.send_text(title='通知：RSS 任务运行成功！', message=msg)
    return msg


@shared_task(bind=True, base=BaseTask)
def auto_torrents_package_files(self):
    """
    拆包并下载
    :param self:
    :return:
    """
    cache_package_files_list = cache.get(f'cache_package_files_list')
    if not cache_package_files_list or len(cache_package_files_list) <= 0:
        logger.info('没有任务，我去玩耍了，一会儿再来！')
        pass
    else:
        for index, package in enumerate(cache_package_files_list):
            try:
                client, _ = toolbox.get_downloader_instance(package.get("downloader_id"))
                # 拆包
                hash_list = package.get("hash_list")
                packaged_hashes = []
                for hash_string in hash_list:
                    try:
                        toolbox.package_files(client=client, hash_string=hash_string)
                    except Exception as e:
                        logger.error(traceback.format_exc(3))
                    finally:
                        packaged_hashes.append(hash_string)
                # 开始下载
                if len(packaged_hashes) == len(hash_list):
                    # 拆包完成的任务从列表中移除
                    del cache_package_files_list[index]
                    msg = f"{package.get('site')} {package.get('time')}拆包结束，开始下载"
                    logger.info(msg)
                else:
                    msg = f"{package.get('site')} {package.get('time')}拆包结束，部分种子操作失败，下次重试，现在开始下载已拆包种子"
                    logger.info(msg)
                torrents = client.torrents_info(status_filter='paused')
                if len(torrents) > 0:
                    for torrent in torrents:
                        try:
                            toolbox.package_files(client=client, hash_string=torrent.get('hash'))
                        except Exception as e:
                            logger.error(e)
                            continue
                client.torrents_resume(torrent_hashes=packaged_hashes)
                msg = f"{package.get('site')} {package.get('time')}推送的种子拆包完成，开始下载"
                logger.info(msg)
            except Exception as e:
                logger.error(traceback.format_exc(3))
                continue
        toolbox.send_text(title='拆包', message=f'拆包任务执行结束！{time.strftime("%Y-%m-%d %H:%M:%S")} \n')


@shared_task(bind=True, base=BaseTask)
def auto_remove_brush_task(self):
    my_site_list = MySite.objects.filter(Q(brush_rss=True) | Q(brush_free=True),
                                         remove_torrent_rules__startswith='{').all()
    message_list = []
    for my_site in my_site_list:
        hash_list = cache.get(f'brush-{my_site.id}-{my_site.nickname}')
        if not hash_list or len(hash_list) <= 0:
            continue
        msg = toolbox.remove_torrent_by_site_rules(my_site.id, hash_list)
        logger.info(msg)
        message_list.append(msg)
    message = ' \n' + '\n > '.join(message_list)
    logger.info(message)
    toolbox.send_text(title='刷流删种', message=message)
    return message


@shared_task(bind=True, base=BaseTask)
def auto_get_rss_torrent_detail(self, my_site_id: int = None):
    if not my_site_id:
        my_site_list = MySite.objects.filter(brush_free=True, rss__contains='http').all()
    else:
        my_site_list = MySite.objects.filter(id=my_site_id, brush_free=True, rss__contains='http').all()
    if len(my_site_list) <= 0:
        return '没有站点需要RSS，请检查RSS链接与抓种开关！'
    website_list = WebSite.objects.all()
    results = pool.map(toolbox.parse_rss, [my_site.rss for my_site in my_site_list])
    for my_site, result in zip(my_site_list, results):
        try:
            website = website_list.get(id=my_site.site)
            hash_list = []
            urls = []
            updated = 0
            created = 0
            for torrent in result:
                tid = torrent.get('tid')
                urls.append(f'{website.url}{website.page_download.format(tid)}')
                # 组装种子详情页URL 解析详情页信息
                # res_detail = pt_spider.get_torrent_detail(my_site, f'{website.url}{website.page_detail.format(tid)}')
                # 如果无报错，将信息合并到torrent
                # if res_detail.code == 0:
                #     torrent.update(res_detail.data)
                res = TorrentInfo.objects.update_or_create(
                    site=my_site,
                    tid=tid,
                    defaults=torrent,
                )
                if res[1]:
                    created += 1
                else:
                    updated += 1
                logger.info(res)
                hash_list.append(res[0].hash_string)
            if website.func_brush_rss and my_site.brush_rss and my_site.downloader:
                downloader = my_site.downloader
                res = toolbox.push_torrents_to_downloader(
                    downloader_id=my_site.downloader.id,
                    urls=urls,
                    cookie=my_site.cookie,
                )
                if downloader.package_files:
                    client, _ = toolbox.get_downloader_instance(downloader.id)
                    for hash_string in hash_list:
                        toolbox.package_files(
                            client=client,
                            hash_string=hash_string
                        )
                logging.info(res.msg)
            msg = f'{my_site.nickname} 新增种子{created} 个，更新{updated}个'
            logger.info(msg)
            toolbox.send_text(title='RSS', message=msg)
            if len(my_site_list) == 1:
                return {'hash_list': hash_list, 'msg': msg}
        except Exception as e:
            msg = f'{my_site.nickname} RSS获取或解析失败'
            logger.error(msg)
            logger.error(traceback.format_exc(3))
            if len(my_site_list) == 1:
                return msg
            continue


@shared_task(bind=True, base=BaseTask)
def auto_get_update_torrent(self, torrent_id):
    if isinstance(torrent_id, str):
        torrent_ids = torrent_id.split('|')
        torrent_list = TorrentInfo.objects.filter(id__in=torrent_ids).all()
    else:
        torrent_list = TorrentInfo.objects.filter(state=False).all()
    count = 0
    for torrent in torrent_list:
        try:
            res = pt_spider.get_update_torrent(torrent)
            if res.code == 0:
                count += 1
        except Exception as e:
            logger.error(traceback.format_exc(3))
            continue
    msg = f'共有{len(torrent_list)}种子需要更新，本次更新成功{count}个，失败{len(torrent_list) - count}个'
    logger.info(msg)


@shared_task(bind=True, base=BaseTask)
def auto_push_to_downloader(self, ):
    """推送到下载器"""
    start = time.time()
    print('推送到下载器')
    end = time.time()
    message = f'> 签到 任务运行成功！耗时：{end - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")}'
    toolbox.send_text(title='通知：推送种子任务', message=message)
    # 释放内存
    gc.collect()


@shared_task(bind=True, base=BaseTask)
def auto_update_torrent_info(self, ):
    """自动获取种子"""
    start = time.time()
    print('自动获取种子HASH')
    time.sleep(5)
    end = time.time()
    message = f'> 获取种子HASH 任务运行成功！耗时：{end - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")}'
    toolbox.send_text(title='通知：自动获取种子HASH', message=message)
    # 释放内存
    gc.collect()


@shared_task(bind=True, base=BaseTask)
def exec_command(self, commands):
    """执行命令行命令"""
    result = []
    for key, command in commands.items():
        p = subprocess.run(command, shell=True)
        logger.info('{} 命令执行结果：\n{}'.format(key, p))
        result.append({
            'command': key,
            'res': p.returncode
        })
    # 释放内存
    gc.collect()
    return result


@shared_task(bind=True, base=BaseTask)
def auto_program_upgrade(self, ):
    """程序更新"""
    try:
        logger.info('开始自动更新')
        update_commands = {
            # 'cp db/db.sqlite3 db/db.sqlite3-$(date "+%Y%m%d%H%M%S")',
            '更新依赖环境': 'wget -O requirements.txt https://gitee.com/ngfchl/ptools/raw/master/requirements.txt &&'
                            ' pip install -r requirements.txt -U',
            '强制覆盖本地': 'git clean -df && git reset --hard',
            '获取更新信息': 'git fetch --all',
            '拉取代码更新': f'git pull origin {os.getenv("DEV")}',
        }
        logger.info('拉取最新代码')
        result = exec_command(update_commands)
        logger.info('更新完毕')
        message = f'> 更新完成！！请在接到通知后同步数据库！{datetime.now()}'
        toolbox.send_text(title='通知：程序更新', message=message)
        return CommonResponse.success(
            msg='更新成功！稍后请在接到通知后同步数据库！！',
            data={
                'result': result
            }
        )
    except Exception as e:
        # raise
        msg = '更新失败!{}，请尝试同步数据库！'.format(str(e))
        logger.error(msg)
        message = f'> <font color="red">{msg}</font>'
        toolbox.send_text(title=msg, message=message)
        return CommonResponse.error(
            msg=msg
        )
    finally:
        # 释放内存
        gc.collect()


@shared_task(bind=True, base=BaseTask)
def auto_update_license(self, ):
    """auto_update_license"""
    res = toolbox.generate_config_file()
    if res.code != 0:
        return CommonResponse.error(
            msg=res.msg
        )
    data = toml.load('db/ptools.toml')
    print(data)
    pt_helper = data.get('pt_helper')
    if len(pt_helper) <= 0:
        return CommonResponse.error(
            msg='请先配置小助手相关信息再进行操作！'
        )
    host = pt_helper.get('host')
    username = pt_helper.get('username')
    password = pt_helper.get('password')
    url = 'http://get_pt_helper_license.guyubao.com/getTrial'
    license_xpath = '//h2/text()'
    session = requests.Session()
    res = session.get(url=url)
    token = ''.join(etree.HTML(res.content).xpath(license_xpath))
    login_url = host + '/login/submit'
    login_res = session.post(
        url=login_url,
        data={
            'username': username,
            'password': password,
        }
    )
    token_url = host + '/sys/config/update'
    logger.info(login_res.cookies.get_dict())
    cookies = session.cookies.get_dict()
    logger.info(cookies)
    res = session.post(
        url=token_url,
        cookies=cookies,
        data={
            'Id': 4,
            'ParamKey': 'license',
            'ParamValue': token.split('：')[-1],
            'Status': 1,
        }
    )
    logger.info(f'结果：{res.text}')
    result = res.json()
    if result.get('code') == 0:
        result['data'] = token
        toolbox.send_text(title='小助手License更新成功！', message=f'> {token}')
        return CommonResponse.success(
            data=result
        )
    # 释放内存
    gc.collect()
    return CommonResponse.error(
        msg=f'License更新失败！'
    )


@shared_task(bind=True, base=BaseTask)
def import_from_ptpp(self, data_list: List):
    results = pool.map(pt_spider.get_uid_and_passkey, data_list)

    message_list = [result.msg for result in results]
    logger.info(message_list)
    # send_text(title='PTPP站点导入通知', message='Cookies解析失败，请确认导入了正确的cookies备份文件！')
    toolbox.send_text(title='PTPP站点导入通知', message='\n\n'.join(message_list))
    return message_list
