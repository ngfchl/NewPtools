from django.db import models

from auxiliary.base import BaseEntity


# Create your models here.
class Task(models.TextChoices):
    # 已实现的自动任务
    backend_cleanup = 'celery.backend_cleanup', '清理任务记录'
    auto_sign_in = 'schedule.tasks.auto_sign_in', '执行签到'
    auto_get_status = 'schedule.tasks.auto_get_status', '更新个人数据'
    auto_get_rss = 'schedule.tasks.auto_get_rss', 'RSS刷流'
    auto_get_torrents = 'schedule.tasks.auto_get_torrents', 'Free刷流'
    # auto_push_to_downloader = 'schedule.tasks.auto_push_to_downloader', '推送种子'
    # auto_torrents_package_files = 'schedule.tasks.auto_torrents_package_files', '拆包任务'
    auto_remove_brush_task = 'schedule.tasks.auto_remove_brush_task', '删种任务'
    auto_cleanup_not_registered = 'schedule.tasks.auto_cleanup_not_registered', '清理废弃种子-刷流'
    auto_get_hash_by_category = 'schedule.tasks.auto_get_hash_by_category', '完善种子HASH'
    auto_reload_supervisor = 'schedule.tasks.auto_reload_supervisor', '自动重载任务'
    # auto_program_upgrade = 'schedule.tasks.auto_program_upgrade', '程序更新'
    # auto_update_torrent_info = 'schedule.tasks.auto_update_torrent_info', '自动获取种子HASH'
    # auto_update_license = 'schedule.tasks.auto_update_license', 'auto_update_license'
    # auto_remove_expire_torrents = 'schedule.tasks.auto_remove_expire_torrents', '删除过期种子'
