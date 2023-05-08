from ninja import ModelSchema, Schema

from website.models import *


class WebSiteMonkeySchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    class Config:
        model = WebSite
        model_exclude = [
            'url', 'nickname', 'logo', 'tags',
            'tracker', 'sp_full', 'nickname', 'limit_speed',
            'func_sign_in', 'func_brush_free', 'func_get_userinfo',
            'func_hr_discern', 'func_repeat_torrents',
            'func_brush_rss', 'func_search_torrents', 'page_index',
            'page_torrents', 'page_sign_in',
            'page_control_panel', 'page_detail', 'page_download',
            'page_user', 'page_search',
            'page_message', 'page_hr', 'page_leeching', 'page_uploaded',
            'page_seeding', 'page_completed', 'page_mybonus', 'page_viewfilelist',
            'sign_info_title', 'sign_info_content', 'hr', 'hr_rate',
            'hr_time', 'search_params', 'created_at', 'updated_at'
        ]


class MySiteSchemaIn(Schema):
    user_id: str
    site: int
    cookie: str
    user_agent: str
    nickname: str
    # token: str


class SiteAndTokenSchemaIn(Schema):
    token: str
    host: str


class CommonMessage(Schema):
    msg: str = ''
    code: int = 0
