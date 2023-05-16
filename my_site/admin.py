from django.contrib import admin

from .models import *


# # Register your models here.

@admin.register(MySite)
class MySiteAdmin(admin.ModelAdmin):
    pass


#
#
@admin.register(SiteStatus)
class SiteStatusAdmin(admin.ModelAdmin):
    pass


#
#
@admin.register(SignIn)
class SignInAdmin(admin.ModelAdmin):
    pass


@admin.register(TorrentInfo)
class TorrentInfoAdmin(admin.ModelAdmin):
    pass
