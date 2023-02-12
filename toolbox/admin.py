from django.contrib import admin

from toolbox.models import *


# Register your models here.

@admin.register(Notify)
class NotifyAdmin(admin.ModelAdmin):
    pass


@admin.register(BaiduOCR)
class BaiduOCRAdmin(admin.ModelAdmin):
    pass
