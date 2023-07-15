# Generated by Django 4.2.1 on 2023-07-06 20:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('my_site', '0006_alter_sitestatus_seed_volume'),
    ]

    operations = [
        migrations.AddField(
            model_name='mysite',
            name='mirror',
            field=models.URLField(blank=True, help_text='必须带最后的 /', null=True, verbose_name='镜像网址'),
        ),
        migrations.AddField(
            model_name='mysite',
            name='mirror_switch',
            field=models.BooleanField(default=False, verbose_name='镜像开关'),
        ),
    ]