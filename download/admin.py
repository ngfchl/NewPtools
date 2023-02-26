from django.contrib import admin

from download.models import *


# Register your models here.

@admin.register(Downloader)
class DownloaderAdmin(admin.ModelAdmin):
    pass
