from django.contrib import admin

from website.models import *


# Register your models here.

@admin.register(WebSite)
class WebSiteAdmin(admin.ModelAdmin):
    pass


@admin.register(UserLevelRule)
class UserLevelRuleAdmin(admin.ModelAdmin):
    pass
