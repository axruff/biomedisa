# Generated by Django 3.0.4 on 2020-03-22 16:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('biomedisa_app', '0060_auto_20200322_1651'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mushroomspot',
            name='status_klopapier',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='mushroomspot',
            name='status_mehl',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='mushroomspot',
            name='status_nudeln',
            field=models.TextField(null=True),
        ),
    ]