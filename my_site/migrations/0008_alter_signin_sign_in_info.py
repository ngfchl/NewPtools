# Generated by Django 4.1.7 on 2023-05-03 19:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('my_site', '0007_rename_on_release_torrentinfo_published_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signin',
            name='sign_in_info',
            field=models.TextField(default='', verbose_name='信息'),
        ),
    ]
