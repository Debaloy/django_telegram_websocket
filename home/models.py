from django.db import models

# Create your models here.
class User(models.Model):
    api_key = models.CharField(primary_key=True, max_length=256)
    api_calls = models.IntegerField(default=0)

    last_user_id_sent = models.CharField(max_length=256, default='')
    last_msg_id_sent = models.CharField(max_length=256, default='')