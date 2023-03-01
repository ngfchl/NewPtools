from ninja import ModelSchema
from ninja.orm import create_schema

from website.models import *


class WebSiteSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    class Config:
        model = WebSite
        model_fields = [
            'id',  'name', 'nickname',
            'logo', 'tags', 'sp_full',
            # 常用地址
            'page_message','url',
            # 功能菜单
            'func_sign_in',
            'func_get_userinfo',
            'func_get_torrents',
            'func_hr_discern',
            'func_brush_flow',
            'func_search_torrents',
            'func_repeat_torrents',
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
