import asyncio
import json
import logging
import traceback

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from my_site.models import MySite
from spider.views import PtSpider
from ws.views import search_and_parse_torrents

pt_spider = PtSpider()
logger = logging.getLogger('ptools')


class ProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            print("已连接")
            """
            """
            await self.accept()

        except Exception as e:
            # 输出异常信息
            print(traceback.format_exc())

    async def disconnect(self, close_code):
        print("已断开")
        pass

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        print(text_data)
        key = text_data_json['key']
        site_list = text_data_json['site_list']
        my_site_list = await self.get_my_site_list(site_list)  # Use the async function
        tasks = [search_and_parse_torrents(my_site, key) for my_site in my_site_list]

        for completed_future in asyncio.as_completed(tasks):
            result = await completed_future
            if result.code == 0:
                logger.info(result.msg)
            else:
                logger.warning(result.msg)
            await self.send(text_data=json.dumps(result.to_dict()))
 
    @database_sync_to_async
    def get_my_site_list(self, site_list):  # This is a synchronous function
        return list(MySite.objects.filter(id__in=site_list, search_torrents=True) if len(
            site_list) > 0 else MySite.objects.filter(search_torrents=True))
