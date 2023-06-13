import asyncio
import logging
import re
import ssl
import time
import traceback
from urllib.parse import urlparse, parse_qs

import aiohttp
from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404
from lxml import etree

from my_site.models import MySite
from toolbox import views as toolbox
from toolbox.schema import CommonResponse
from website.models import WebSite

logger = logging.getLogger('ptools')


async def send_request(my_site: MySite,
                       url: str,
                       method: str = 'get',
                       data: dict = None,
                       params: dict = None,
                       json: dict = None,
                       timeout: int = 75,
                       delay: int = 15,
                       header: dict = {}):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    _RESTRICTED_SERVER_CIPHERS = 'ALL'
    ssl_context.set_ciphers(_RESTRICTED_SERVER_CIPHERS)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    headers = {
        'User-Agent': my_site.user_agent,
    }
    proxy = my_site.custom_server
    proxies = {
        'http': proxy if proxy else None,
        'https': proxy if proxy else None,
    } if proxy else None
    headers.update(header)

    timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout,
                                     cookies=toolbox.cookie2dict(my_site.cookie)) as session:
        if method.lower() == "get":
            response = await session.get(url, params=params, ssl=ssl_context)
        elif method.lower() == "post":
            response = await session.post(url, data=data, json=json, ssl=ssl_context)
        else:
            # Handle other HTTP methods if necessary
            pass

        await asyncio.sleep(delay)
        return response


@database_sync_to_async
def get_website(my_site):  # This is a synchronous function
    return get_object_or_404(WebSite, id=my_site.site)


def parse(html_text, rules):
    return etree.HTML(html_text).xpath(rules)


async def search_and_parse_torrents(my_site: MySite, key: str):
    site = await get_website(my_site)  # Use the async function
    url = f'{site.url}{site.page_search.format(key)}'
    logger.info(f"{site.name} 开始搜索")
    torrents = []
    # Asynchronous HTTP request with aiohttp
    try:
        response = await send_request(my_site, url)
        if response.status == 200:
            try:
                logger.info(f"{site.name} 开始解析搜索结果")
                html_text = await response.text()
                trs = parse(html_text, site.torrents_rule)
                logger.info(f'{my_site.nickname} 共发现{len(trs)}条种子记录')
                logger.info('=' * 50)
                for tr in trs:
                    logger.debug(tr)
                    # logger.debug(etree.tostring(tr))
                    sale_status = ''.join(tr.xpath(site.torrent_sale_rule))
                    logger.debug('sale_status: {}'.format(sale_status))

                    title_list = tr.xpath(site.torrent_subtitle_rule)
                    logger.debug(title_list)
                    subtitle = ''.join(title_list).strip('剩余时间：').strip('剩餘時間：').replace(
                        '&nbsp;', '').strip('()').strip()
                    title = ''.join(tr.xpath(site.torrent_title_rule)).replace('&nbsp;', '').strip()
                    if not title and not subtitle:
                        logger.error('无名无姓？跳过')
                        continue
                    # sale_status = ''.join(re.split(r'[^\x00-\xff]', sale_status))
                    sale_status = sale_status.replace('tStatus ', '').upper().replace(
                        'FREE', 'Free'
                    ).replace('免费', 'Free').replace(' ', '')
                    # # 下载链接，下载链接已存在则跳过
                    href = ''.join(tr.xpath(site.torrent_magnet_url_rule))
                    logger.debug('href: {}'.format(href))
                    magnet_url = '{}{}'.format(
                        site.url,
                        href.replace('&type=zip', '').replace(site.url, '').lstrip('/')
                    )
                    parsed_url = urlparse(magnet_url)
                    tid = parse_qs(parsed_url.query).get("id")[0]
                    logger.info('magnet_url: {}'.format(magnet_url))
                    # 如果种子有HR，则为否 HR绿色表示无需，红色表示未通过HR考核
                    hr = False if tr.xpath(site.torrent_hr_rule) else True
                    # H&R 种子有HR且站点设置不下载HR种子,跳过，
                    if not hr and not my_site.hr_discern:
                        logger.debug('hr种子，未开启HR跳过')
                    # # 促销到期时间
                    sale_expire = ''.join(tr.xpath(site.torrent_sale_expire_rule))
                    if site.url in [
                        'https://www.beitai.pt/',
                        'http://www.oshen.win/',
                        'https://www.hitpt.com/',
                        'https://hdsky.me/',
                        'https://pt.keepfrds.com/',
                        # 'https://totheglory.im/',
                    ]:
                        """
                        由于备胎等站优惠结束日期格式特殊，所以做特殊处理,使用正则表达式获取字符串中的时间
                        """
                        sale_expire = ''.join(
                            re.findall(r'\d{4}\D\d{2}\D\d{2}\D\d{2}\D\d{2}\D', ''.join(sale_expire)))

                    if site.url in [
                        'https://totheglory.im/',
                    ]:
                        # javascript: alert('Freeleech将持续到2022年09月20日13点46分,加油呀~')
                        # 获取时间数据
                        time_array = re.findall(r'\d+', ''.join(sale_expire))
                        # 不组9位
                        time_array.extend([0, 0, 0, 0])
                        # 转化为标准时间字符串
                        sale_expire = time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.struct_time(tuple([int(x) for x in time_array]))
                        )
                    logger.debug(sale_expire)
                    if sale_expire.endswith(':'):
                        sale_expire = sale_expire + '00'
                    # 如果促销结束时间为空，则为无限期
                    sale_expire = None if not sale_expire else sale_expire
                    # logger.debug(torrent_info.sale_expire)
                    # 发布时间
                    on_release = ''.join(tr.xpath(site.torrent_release_rule))
                    # 做种人数
                    seeders = ''.join(tr.xpath(site.torrent_seeders_rule)).replace(',', '')
                    # 下载人数
                    leechers = ''.join(tr.xpath(site.torrent_leechers_rule)).replace(',', '')
                    # 完成人数
                    completers = ''.join(tr.xpath(site.torrent_completers_rule)).replace(',', '')
                    # 存在则更新，不存在就创建
                    # logger.debug(type(seeders), type(leechers), type(completers), )
                    # logger.debug(seeders, leechers, completers)
                    # logger.debug(''.join(tr.xpath(site.title_rule)))
                    category = ''.join(tr.xpath(site.torrent_category_rule))
                    file_parse_size = ''.join(tr.xpath(site.torrent_size_rule))
                    # file_parse_size = ''.join(tr.xpath(''))
                    logger.debug(file_parse_size)
                    file_size = toolbox.FileSizeConvert.parse_2_byte(file_parse_size)
                    # subtitle = subtitle if subtitle else title
                    poster_url = ''.join(tr.xpath(site.torrent_poster_rule))  # 海报链接
                    logger.debug(f'title：{title}\n size: {file_size}\n category：{category}\n '
                                 f'magnet_url：{magnet_url}\n subtitle：{subtitle}\n sale_status：{sale_status}\n '
                                 f'sale_expire：{sale_expire}\n seeders：{seeders}\n leechers：{leechers}\n'
                                 f'H&R：{hr}\n completers：{completers}')
                    torrent = {
                        'site': my_site.site,
                        'tid': tid,
                        'poster_url': poster_url,
                        'category': category,
                        'magnet_url': magnet_url,
                        'detail_url': f'{site.url}{site.page_detail.format(tid)}',
                        'title': title,
                        'subtitle': subtitle,
                        'sale_status': sale_status,
                        'sale_expire': sale_expire,
                        'hr': hr,
                        'published': on_release,
                        'size': file_size,
                        'seeders': int(seeders) if seeders else 0,
                        'leechers': int(leechers) if leechers else 0,
                        'completers': int(completers) if completers else 0,
                    }
                    torrents.append(torrent)
                msg = f"{site.name} 共{len(torrents)}个结果！"
                logger.info(msg)
                if len(torrents) > 0:
                    return CommonResponse.success(data={
                        "site": site.id,
                        "torrents": torrents
                    }, msg=msg)
                return CommonResponse.error(msg=msg)
            except Exception as e:
                # raise
                title = f'{site.name} 解析种子信息：失败！'
                msg = f'{site.name} 解析种子页面失败！{e}'
                # toolbox.send_text(title=title, message=msg)
                logger.error(msg)
                logger.error(traceback.format_exc(limit=3))
                return CommonResponse.error(msg=msg)
        elif response.status == 503:
            return CommonResponse.error(msg=f"{site.name} 我可能碰上CF盾了")
        else:
            return CommonResponse.error(msg=f"{site.name} 网站访问失败")
    except Exception as e:
        # raise
        title = f'{site.name} 网站访问失败'
        msg = f'{site.name} 网站访问失败！原因：{e}'
        # 打印异常详细信息
        logger.error(msg)
        logger.error(traceback.format_exc(limit=3))
        # toolbox.send_text(title=title, message=msg)
        return CommonResponse.error(msg=msg)
