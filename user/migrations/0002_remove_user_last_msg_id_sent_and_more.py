# Generated by Django 4.2 on 2023-05-17 10:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='last_msg_id_sent',
        ),
        migrations.RemoveField(
            model_name='user',
            name='last_user_id_sent',
        ),
    ]