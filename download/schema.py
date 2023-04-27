from typing import List, Optional, Union

from ninja import ModelSchema, Schema

from download.models import Downloader


class DownloaderSchemaOut(ModelSchema):
    """返回下载器基本信息"""

    class Config:
        model = Downloader
        model_fields = ['id', 'name', 'host', 'category', 'enable', 'port']


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
        model_exclude = ['created_at', 'updated_at']


class CategorySchema(Schema):
    """返回下载器分类/下载路径"""
    name: str
    savePath: str


class ControlTorrentCommandIn(Schema):
    """接收QB控制指令"""
    ids: List[str]
    command: str
    delete_files: bool
    category: Optional[str]
    enable: bool
    downloader_id: int


class NewTorrent(Schema):
    urls: Optional[Union[str, List[str]]]
    cookie: Optional[str] = ''
    category: Optional[str] = ''
    is_paused: bool = False
    upload_limit: Optional[int] = 0
    download_limit: Optional[int] = 0
    is_skip_checking: bool = False
    use_auto_torrent_management: bool = True


class AddTorrentCommandIn(Schema):
    downloader_id: int
    new_torrent: NewTorrent
