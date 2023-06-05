from django.contrib import admin

from configuration.models import Notify


# Register your models here.
@admin.register(Notify)
class NotifyAdmin(admin.ModelAdmin):
    pass
