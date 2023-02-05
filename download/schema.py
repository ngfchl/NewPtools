from ninja import ModelSchema, Schema

from download.models import Downloader


class DownloaderSchemaOut(ModelSchema):
    """返回下载器基本信息"""

    class Config:
        model = Downloader
        model_fields = ['id', 'name', 'host', 'category']


class CategorySchema(Schema):
    """返回下载器分类/下载路径"""
    category: str


class ControlTorrentCommandIn(Schema):
    """接收QB控制指令"""
    ids: str
    command: str
    delete_files: bool
    category: str
    enable: bool
    downloader_id: int
