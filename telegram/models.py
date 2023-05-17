from django.db import models

# Create your models here.
class Telegram(models.Model):
    api_key = models.CharField(max_length=256, default='')
    group_name = models.CharField(max_length=128, default='')
    message_id = models.CharField(max_length=64, default='')