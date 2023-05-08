from django.db import models

from auxiliary.base import BaseEntity


# Create your models here.
class Task(models.TextChoices):
    # 已实现的自动任务
    backend_cleanup = 'celery.backend_cleanup', '清理任务记录'
    auto_sign_in = 'schedule.tasks.auto_sign_in', '执行签到'
    auto_get_status = 'schedule.tasks.auto_get_status', '更新个人数据'
    auto_get_torrents = 'schedule.tasks.auto_get_torrents', '拉取最新种子'
    # auto_program_upgrade = 'schedule.tasks.auto_program_upgrade', '程序更新'
    # auto_get_torrent_hash = 'schedule.tasks.auto_get_torrent_hash', '自动获取种子HASH'
    # auto_push_to_downloader = 'schedule.tasks.auto_push_to_downloader', '推送到下载器'
    auto_update_license = 'schedule.tasks.auto_update_license', 'auto_update_license'
    # auto_remove_expire_torrents = 'schedule.tasks.auto_remove_expire_torrents', '删除过期种子'
    auto_get_rss = 'schedule.tasks.auto_get_rss', 'auto_get_rss'
