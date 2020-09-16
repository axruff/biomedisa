# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-10-04 16:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('biomedisa_app', '0025_auto_20181001_1631'),
    ]

    operations = [
        migrations.AlterField(
            model_name='upload',
            name='ac_alpha',
            field=models.FloatField(default=1.0, verbose_name='Active contour alpha'),
        ),
        migrations.AlterField(
            model_name='upload',
            name='ac_smooth',
            field=models.IntegerField(default=1, verbose_name='Active contour smooth'),
        ),
        migrations.AlterField(
            model_name='upload',
            name='ac_steps',
            field=models.IntegerField(default=3, verbose_name='Active contour steps'),
        ),
    ]