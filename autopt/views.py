import logging
import time
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime

from my_site.models import MySite, TorrentInfo
from my_site.views import pt_spider, MessageTemplate
from toolbox import views as toolbox

# Create your views here.

logger = logging.getLogger('ptools')
pool = ThreadPoolExecutor(2)


def auto_sign_in():
    """自动签到"""
    start = time.time()
    # 获取工具支持且本人开启签到的所有站点
    queryset = MySite.objects.filter(site__sign_in_support=True).filter(sign_in=True).all()
    message_list = pt_spider.do_sign_in(pool, queryset)
    end = time.time()
    consuming = '> <font  color="blue">{} 任务运行成功！耗时：{}完成时间：{}  </font>\n'.format(
        '自动签到', end - start,
        time.strftime("%Y-%m-%d %H:%M:%S")
    )

    if message_list == 0:
        logger.info('已经全部签到咯！！')
    else:
        logger.info(message_list + consuming)
        message = message_list + consuming
        pt_spider.send_text(title='通知：自动签到', message=message)
    logger.info('{} 任务运行成功！完成时间：{}'.format('自动签到', time.strftime("%Y-%m-%d %H:%M:%S")))


def auto_get_status():
    """
    更新个人数据
    """
    start = time.time()
    message_list = '# 更新个人数据  \n\n'
    queryset = MySite.objects.all()
    site_list = [my_site for my_site in queryset if my_site.site.get_userinfo_support]
    results = pool.map(pt_spider.send_status_request, site_list)
    message_template = MessageTemplate.status_message_template
    for my_site, result in zip(site_list, results):
        if result.code == 0:
            res = pt_spider.parse_status_html(my_site, result.data)
            logger.info('自动更新个人数据: {}, {}'.format(my_site.site, res))
            if res.code == 0:
                status = res.data[0]
                message = message_template.format(
                    my_site.site.name,
                    my_site.my_level,
                    status.my_sp,
                    status.sp_hour,
                    status.my_bonus,
                    status.ratio,
                    toolbox.FileSizeConvert.parse_2_file_size(status.seed_vol),
                    toolbox.FileSizeConvert.parse_2_file_size(status.uploaded),
                    toolbox.FileSizeConvert.parse_2_file_size(status.downloaded),
                    status.seed,
                    status.leech,
                    status.invitation,
                    my_site.my_hr
                )
                logger.info('组装Message：{}'.format(message))
                message_list += (
                        '> <font color="orange">' + my_site.site.name + '</font> 信息更新成功！' + message + '  \n\n')
                # pt_spider.send_text(my_site.site.name + ' 信息更新成功！' + message)
                logger.info(my_site.site.name + '信息更新成功！' + message)
            else:
                print(res)
                message = '> <font color="red">' + my_site.site.name + ' 信息更新失败！原因：' + res.msg + '</font>  \n\n'
                message_list = message + message_list
                # pt_spider.send_text(my_site.site.name + ' 信息更新失败！原因：' + str(res[0]))
                logger.warning(my_site.site.name + '信息更新失败！原因：' + res.msg)
        else:
            # pt_spider.send_text(my_site.site.name + ' 信息更新失败！原因：' + str(result[1]))
            message = '> <font color="red">' + my_site.site.name + ' 信息更新失败！原因：' + result.msg + '</font>  \n\n'
            message_list = message + message_list
            logger.warning(my_site.site.name + '信息更新失败！原因：' + result.msg)
    # 发送今日数据
    pt_spider.today_data()
    end = time.time()
    consuming = '> <font color="blue">{} 任务运行成功！耗时：{} 完成时间：{}  </font>  \n'.format(
        '自动更新个人数据', end - start,
        time.strftime("%Y-%m-%d %H:%M:%S")
    )
    logger.info(message_list + consuming)
    message = message_list + consuming
    pt_spider.send_text(title='通知：更新个人数据', message=message)


def auto_update_torrents():
    """
    拉取最新种子
    """
    start = time.time()
    message_list = '# 拉取免费种子  \n\n'
    queryset = MySite.objects.all()
    site_list = [my_site for my_site in queryset if my_site.site.get_torrent_support]
    results = pool.map(pt_spider.send_torrent_info_request, site_list)
    for my_site, result in zip(site_list, results):
        logger.info('获取种子：{}{}'.format(my_site.site.name, result))
        # print(result is tuple[int])
        if result.code == 0:
            res = pt_spider.get_torrent_info_list(my_site, result.data)
            # 通知推送
            if res.code == 0:
                message = '> <font color="orange">{}</font> 种子抓取成功！新增种子{}条，更新种子{}条!  \n\n'.format(
                    my_site.site.name,
                    res.data[0],
                    res.data[1])
                message_list += message
            else:
                message = '> <font color="red">' + my_site.site.name + '抓取种子信息失败！原因：' + res.msg + '</font>  \n'
                message_list = message + message_list
            # 日志
            logger.info(
                '{} 种子抓取成功！新增种子{}条，更新种子{}条! '.format(my_site.site.name, res.data[0], res.data[
                    1]) if res.code == 0 else my_site.site.name + '抓取种子信息失败！原因：' + res.msg)
        else:
            # pt_spider.send_text(my_site.site.name + ' 抓取种子信息失败！原因：' + result[0])
            message = '> <font color="red">' + my_site.site.name + ' 抓取种子信息失败！原因：' + result.msg + '</font>  \n'
            message_list = message + message_list
            logger.info(my_site.site.name + '抓取种子信息失败！原因：' + result.msg)
    end = time.time()
    consuming = '> {} 任务运行成功！耗时：{} 当前时间：{}  \n'.format(
        '拉取最新种子',
        end - start,
        time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(message_list + consuming)
    message = message_list + consuming
    pt_spider.send_text(title='通知：拉取最新种子', message=message)


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
    pt_spider.send_text(title='通知：清除种子任务', message=message)
