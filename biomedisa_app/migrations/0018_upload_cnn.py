# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-05-17 11:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('biomedisa_app', '0017_upload_ignore'),
    ]

    operations = [
        migrations.AddField(
            model_name='upload',
            name='cnn',
            field=models.BooleanField(default=False, verbose_name='CNN'),
        ),
    ]