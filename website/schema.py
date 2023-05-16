from ninja import ModelSchema
from ninja.orm import create_schema

from website.models import *


class WebSiteSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    class Config:
        model = WebSite
        model_fields = [
            'id', 'name', 'nickname',
            'logo', 'tags', 'sp_full',
            'tracker',
            # 常用地址
            'page_message', 'url',
            # 功能菜单
            'sign_in',
            'get_info',
            'brush_free',
            'hr_discern',
            'brush_rss',
            'search_torrents',
            'repeat_torrents',
        ]


class WebSiteSchemaIn(ModelSchema):
    class Config:
        model = WebSite
        model_exclude = ['created_at', 'updated_at']


class UserLevelRuleSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """
    site: create_schema(model=WebSite, fields=['id', 'name'])

    class Config:
        model = UserLevelRule
        model_exclude = ['created_at', 'updated_at']


class TrackerSchema(ModelSchema):
    class Config:
        model = WebSite
        model_fields = ['id', 'name', 'tracker']


class UserLevelRuleSchemaIn(ModelSchema):
    class Config:
        model = UserLevelRule
        model_exclude = ['created_at', 'updated_at']
