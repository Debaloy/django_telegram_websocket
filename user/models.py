from django.db import models

# Create your models here.
from django.db import models

# Create your models here.
class User(models.Model):
    api_key = models.CharField(primary_key=True, max_length=256)
    api_calls = models.IntegerField(default=0)