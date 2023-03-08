from ninja import ModelSchema, Schema

from download.models import Downloader


class DownloaderSchemaOut(ModelSchema):
    """返回下载器基本信息"""

    class Config:
        model = Downloader
        model_fields = ['id', 'name', 'host', 'category']


class TransferSchemaOut(Schema):
    connection_status: bool
    # dht_nodes: int
    dl_info_data: int
    dl_info_speed: int
    # dl_rate_limit: int
    up_info_data: int
    up_info_speed: int
    # up_rate_limit: int
    category: str
    name: str


class DownloaderSchemaIn(ModelSchema):
    """添加下载器"""

    class Config:
        model = Downloader
        model_exclude = ['id', 'created_at', 'updated_at']


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
