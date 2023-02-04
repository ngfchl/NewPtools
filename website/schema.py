from ninja import ModelSchema
from ninja.orm import create_schema

from website.models import *


class WebSiteSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    class Config:
        model = WebSite
        model_fields = ['url', 'name', 'nickname', 'logo', 'tags']


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


class UserLevelRuleSchemaIn(ModelSchema):
    class Config:
        model = UserLevelRule
        model_exclude = ['created_at', 'updated_at']
