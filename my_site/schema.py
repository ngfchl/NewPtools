from typing import Optional

from ninja import ModelSchema, Schema

from my_site.models import *
from website.schema import WebSiteSchemaOut, UserLevelRuleSchemaOut


class MySiteSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    # site: create_schema(WebSite, fields=['id', 'name'])
    updated: str
    joined: str
    downloader_id: Optional[int]

    class Config:
        model = MySite
        model_exclude = [
            'created_at',
            'passkey',
            'cookie',
            'user_agent'
        ]

    def resolve_updated(self, obj):
        return datetime.strftime(self.updated_at, '%Y年%m月%d日%H:%M:%S')

    def resolve_joined(self, obj):
        return datetime.strftime(self.time_join, '%Y年%m月%d日%H:%M:%S')

    def resolve_downloader_id(self, obj):
        if self.downloader:
            return self.downloader.id
        else:
            return None


class MySiteDoSchemaIn(Schema):
    site_id: int
    sort_id: Optional[int]


class MySiteSchemaEdit(ModelSchema):
    # site: create_schema(WebSite, fields=['id', 'name'])
    downloader_id: Optional[int]

    def resolve_downloader_id(self, obj):
        if self.downloader:
            return self.downloader.id
        else:
            return None

    class Config:
        model = MySite
        model_exclude = ['created_at', 'updated_at']


class MySiteSortSchemaIn(ModelSchema):
    # site: create_schema(WebSite, fields=['id', 'name'])
    updated: str

    class Config:
        model = MySite
        model_exclude = ['id', 'sort_id']

    def resolve_updated(self, obj):
        return datetime.strftime(self.updated_at, '%Y年%m月%d日%H:%M:%S')


class SiteStatusSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """
    updated: str
    updated_at: Optional[datetime]

    class Config:
        model = SiteStatus
        model_exclude = ['created_at']

    def resolve_updated(self, obj):
        return datetime.strftime(
            self.updated_at,
            '%Y年%m月%d日%H:%M:%S'
        ) if self.updated_at else datetime.now().strftime('%Y年%m月%d日%H:%M:%S')


class SiteStatusSchemaIn(ModelSchema):
    class Config:
        model = SiteStatus
        model_exclude = ['created_at', 'updated_at']


class SignInSchemaOut(ModelSchema):
    """    站点基本信息及信息抓取规则    """

    updated: str

    class Config:
        model = SignIn
        model_exclude = ['created_at']

    def resolve_updated(self, obj):
        return datetime.strftime(self.updated_at, '%Y年%m月%d日%H:%M:%S')


class StatusSchema(Schema):
    """返回复杂数据"""
    my_site: MySiteSchemaOut
    site: WebSiteSchemaOut
    sign: Optional[SignInSchemaOut]
    status: Optional[SiteStatusSchemaOut]
    level: Optional[UserLevelRuleSchemaOut]
    next_level: Optional[UserLevelRuleSchemaOut]


class SignInSchemaIn(ModelSchema):
    class Config:
        model = SignIn
        model_exclude = ['created_at', 'updated_at']


class TorrentInfoSchemaOut(ModelSchema):
    class Config:
        model = TorrentInfo
        model_exclude = ['created_at', 'updated_at']


class SignInQueryParamsSchemaIn(Schema):
    site_id: int
    page: int
    limit: int


class ImportSchema(Schema):
    info: str
    cookies: str
    # userdata: str
