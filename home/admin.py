from django.contrib import admin
from user.models import User
from telegram.models import Telegram

class UserAdmin(admin.ModelAdmin):
    list_display=('api_key', 'api_calls')

class TelegramAdmin(admin.ModelAdmin):
    list_display=('api_key', 'group_name', 'message_id')

# Register your models here.
admin.site.register(User, UserAdmin)
admin.site.register(Telegram, TelegramAdmin)