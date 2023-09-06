import datetime
from typing import Optional, List

from ninja import ModelSchema, Schema

from website.models import *


class WebSiteMonkeySchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    class Config:
        model = WebSite
        model_exclude = [
            'url', 'nickname', 'logo', 'tags',
            'tracker', 'sp_full', 'nickname', 'limit_speed',
            'sign_in', 'brush_free', 'get_info',
            'hr_discern', 'repeat_torrents',
            'brush_rss', 'search_torrents', 'page_index',
            'page_torrents', 'page_sign_in',
            'page_control_panel', 'page_detail', 'page_download',
            'page_user', 'page_search',
            'page_message', 'page_hr', 'page_leeching', 'page_uploaded',
            'page_seeding', 'page_completed', 'page_mybonus', 'page_viewfilelist',
            'sign_info_title', 'sign_info_content', 'hr', 'hr_rate',
            'hr_time', 'created_at', 'updated_at'
        ]


class MySiteSchemaIn(Schema):
    user_id: str
    site: int
    cookie: str
    user_agent: str
    nickname: str
    passkey: Optional[str]
    time_join: Optional[datetime.datetime]
    # token: str


class SiteAndTokenSchemaIn(Schema):
    token: str
    host: str


class CommonMessage(Schema):
    msg: str = ''
    code: int = 0


class TorrentInfoSchemaIn(Schema):
    tid: int
    site: int
    title: str
    subtitle: Optional[str]
    category: str
    size: str
    tags: Optional[str]
    hr: Optional[str]
    poster: Optional[str]
    magnet_url: str
    douban_url: Optional[str]
    imdb_url: Optional[str]
    release: Optional[datetime.datetime]
    sale_expire: Optional[str]
    sale_status: Optional[str]
    seeders: Optional[int]
    leechers: Optional[int]
    completers: Optional[int]
    hash_string: Optional[str]
    files_count: Optional[int]


class MonkeyTorrentsSchemaIn(Schema):
    site: int
    torrents: List[TorrentInfoSchemaIn]
