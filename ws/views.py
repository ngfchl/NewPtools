import asyncio
import logging
import traceback

import aiohttp
from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404
from lxml import etree

from my_site.models import MySite
from spider.views import PtSpider
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
                       header: dict = dict()):
    headers = {
        'User-Agent': my_site.user_agent,
    }
    headers.update(header)
    proxy = my_site.custom_server

    timeout = aiohttp.ClientTimeout(total=timeout)
    con = aiohttp.TCPConnector(verify_ssl=False)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=con,
                                     cookies=toolbox.cookie2dict(my_site.cookie)) as session:
        if method.lower() == "get":
            response = await session.get(url, params=params, proxy=proxy)
        elif method.lower() == "post":
            response = await session.post(url, data=data, json=json, proxy=proxy)
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
                msg = f'{my_site.nickname} 共发现{len(trs)}条种子记录'
                logger.info(msg)
                if len(trs) <= 0:
                    return CommonResponse.error(msg=msg)
                logger.info('=' * 50)
                for tr in trs:
                    logger.debug(tr)
                    # logger.debug(etree.tostring(tr))
                    try:
                        res = PtSpider.parse_torrent_list(tr, site, my_site)
                        if res.code != 0:
                            logger.error(res.msg)
                            continue
                        torrents.append(res.data)
                    except Exception as e:
                        err_msg = f'当前种子解析出错啦！{e}'
                        logger.info(err_msg)
                        continue
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
                msg = f'{title} {e}'
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
        title = f'{site.name} 网站访问失败！'
        msg = f'{title} 原因：{e}'
        # 打印异常详细信息
        logger.error(msg)
        logger.error(traceback.format_exc(limit=3))
        # toolbox.send_text(title=title, message=msg)
        return CommonResponse.error(msg=msg)
