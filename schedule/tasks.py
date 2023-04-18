from __future__ import absolute_import, unicode_literals

import gc
import logging
import os
import subprocess
import time
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool
from typing import List

import requests
import toml
from celery.app import shared_task
from lxml import etree

from auxiliary.base import MessageTemplate
from auxiliary.celery import app
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
@app.task
def auto_sign_in(site_list: List[int] = []):
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
    toolbox.send_text(title='通知：自动签到-成功', message='\n'.join(message_list))
    # 释放内存
    gc.collect()
    return message_list


@shared_task
def auto_get_status(site_list: List[int] = []):
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


@shared_task
def auto_get_torrents(site_list: List[int] = []):
    """
    拉取最新种子
    """
    start = time.time()
    message_list = '# 拉取免费种子  \n\n'
    websites = WebSite.objects.all()
    queryset = MySite.objects.filter(id__in=site_list) if len(site_list) > 0 else MySite.objects.all()
    site_list = [my_site for my_site in queryset if websites.get(id=my_site.site).func_get_torrents]
    results = pool.map(pt_spider.send_torrent_info_request, site_list)
    for my_site, result in zip(site_list, results):
        logger.info('获取种子：{}{}'.format(my_site.nickname, result))
        # print(result is tuple[int])
        if result.code == 0:
            res = pt_spider.get_torrent_info_list(my_site, result.data)
            # 通知推送
            if res.code == 0:
                message = '> <font color="orange">{}</font> 种子抓取成功！新增种子{}条，更新种子{}条!  \n\n'.format(
                    my_site.nickname,
                    res.data[0],
                    res.data[1])
                message_list += message
            else:
                message = '> <font color="red">' + my_site.nickname + '抓取种子信息失败！原因：' + res.msg + '</font>  \n'
                message_list = message + message_list
            # 日志
            logger.info(
                '{} 种子抓取成功！新增种子{}条，更新种子{}条! '.format(my_site.nickname, res.data[0], res.data[
                    1]) if res.code == 0 else my_site.nickname + '抓取种子信息失败！原因：' + res.msg)
        else:
            # toolbox.send_text(my_site.nickname + ' 抓取种子信息失败！原因：' + result[0])
            message = '> <font color="red">' + my_site.nickname + ' 抓取种子信息失败！原因：' + result.msg + '</font>  \n'
            message_list = message + message_list
            logger.info(my_site.nickname + '抓取种子信息失败！原因：' + result.msg)
    end = time.time()
    consuming = '> {} 任务运行成功！耗时：{} 当前时间：{}  \n'.format(
        '拉取最新种子',
        end - start,
        time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(message_list + consuming)
    message = message_list + consuming
    toolbox.send_text(title='通知：拉取最新种子', message=message)
    # 释放内存
    gc.collect()


@app.task
def auto_remove_expire_torrents():
    """
    删除过期种子
    """
    start = time.time()
    torrent_info_list = TorrentInfo.objects.all()
    count = 0
    for torrent_info in torrent_info_list:
        logger.info('种子名称：{}'.format(torrent_info.name))
        expire_time = torrent_info.sale_expire
        if '无限期' in expire_time:
            # ToDo 先更新种子信息，然后再判断
            continue
        if expire_time.endswith(':'):
            expire_time += '00'
            torrent_info.sale_expire = expire_time
            torrent_info.save()
        time_now = datetime.now()
        try:
            expire_time_parse = datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
            logger.info('优惠到期时间：{}'.format(expire_time))
        except Exception as e:
            logger.info('优惠到期时间解析错误：{}'.format(e))
            torrent_info.delete()
            count += 1
            continue
        if (expire_time_parse - time_now).days <= 0:
            logger.info('优惠已到期时间：{}'.format(expire_time))
            if torrent_info.downloader:
                # 未推送到下载器，跳过或删除？
                pass
            if pt_spider.get_torrent_info_from_downloader(torrent_info).code == 0:
                # todo 设定任务规则：
                #  免费到期后，下载完毕的种子是删除还是保留？
                #  未下载完成的，是暂停还是删除？
                pass
            count += 1
            torrent_info.delete()
    end = time.time()
    message = f'> 清除种子 任务运行成功！共清除过期种子{count}个，耗时：{end - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")}'
    toolbox.send_text(title='通知：清除种子任务', message=message)
    # 释放内存
    gc.collect()


@shared_task
def auto_push_to_downloader():
    """推送到下载器"""
    start = time.time()
    print('推送到下载器')
    end = time.time()
    message = f'> 签到 任务运行成功！耗时：{end - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")}'
    toolbox.send_text(title='通知：推送种子任务', message=message)
    # 释放内存
    gc.collect()


@shared_task
def auto_get_torrent_hash():
    """自动获取种子HASH"""
    start = time.time()
    print('自动获取种子HASH')
    time.sleep(5)
    end = time.time()
    message = f'> 获取种子HASH 任务运行成功！耗时：{end - start}  \n{time.strftime("%Y-%m-%d %H:%M:%S")}'
    toolbox.send_text(title='通知：自动获取种子HASH', message=message)
    # 释放内存
    gc.collect()


@shared_task
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
    # 释放内存
    gc.collect()
    return result


@shared_task
def auto_program_upgrade():
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


@shared_task
def auto_update_license():
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


@shared_task
def import_from_ptpp(data_list: List):
    results = pool.map(pt_spider.get_uid_and_passkey, data_list)

    message_list = [result.msg for result in results]
    logger.info(message_list)
    # send_text(title='PTPP站点导入通知', message='Cookies解析失败，请确认导入了正确的cookies备份文件！')
    toolbox.send_text(title='PTPP站点导入通知', message='\n\n'.join(message_list))
    return message_list
