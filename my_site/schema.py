from ninja import ModelSchema, Schema
from ninja.orm import create_schema

from my_site.models import *


class MySiteSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    # site: create_schema(WebSite, fields=['id', 'name'])

    class Config:
        model = MySite
        model_exclude = ['created_at']


class MySiteSchemaIn(ModelSchema):
    # site: create_schema(WebSite, fields=['id', 'name'])

    class Config:
        model = MySite
        model_exclude = ['created_at', 'updated_at']


class MySiteSortSchemaIn(ModelSchema):
    # site: create_schema(WebSite, fields=['id', 'name'])

    class Config:
        model = MySite
        model_exclude = ['id', 'sort_id']


class SiteStatusSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """
    site: create_schema(model=MySite, fields=['id'])

    class Config:
        model = SiteStatus
        model_exclude = ['created_at', 'updated_at']


class SiteStatusSchemaIn(ModelSchema):
    class Config:
        model = SiteStatus
        model_exclude = ['created_at', 'updated_at']


class SignInSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """
    site: create_schema(model=MySite, fields=['id'])

    class Config:
        model = SignIn
        model_exclude = ['created_at', 'updated_at']


class SignInSchemaIn(ModelSchema):
    class Config:
        model = SignIn
        model_exclude = ['created_at', 'updated_at']


class TorrentInfoSchemaOut(ModelSchema):
    class Config:
        model = SignIn
        model_exclude = ['created_at', 'updated_at']


class ImportSchema(Schema):
    info: str
    cookies: str
    # userdata: str
