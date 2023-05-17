# Generated by Django 4.2 on 2023-05-17 10:14

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('api_key', models.CharField(max_length=256, primary_key=True, serialize=False)),
                ('api_calls', models.IntegerField(default=0)),
                ('last_user_id_sent', models.CharField(default='', max_length=256)),
                ('last_msg_id_sent', models.CharField(default='', max_length=256)),
            ],
        ),
    ]
