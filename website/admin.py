from django.contrib import admin

from .models import *


# Register your models here.
@admin.register(WebSite)
class WebSiteAdmin(admin.ModelAdmin):
    list_filter = [
        'name', 'nickname',
    ]
    list_display = [
        'name', 'nickname', 'url', 'iyuu'
    ]
    search_fields = ['name']


@admin.register(UserLevelRule)
class UserLevelRuleAdmin(admin.ModelAdmin):
    pass
