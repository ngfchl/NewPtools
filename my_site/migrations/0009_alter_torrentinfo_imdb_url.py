# Generated by Django 4.2.1 on 2023-08-25 13:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('my_site', '0008_remove_torrentinfo_area_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='torrentinfo',
            name='imdb_url',
            field=models.URLField(default='', verbose_name='imdb'),
        ),
    ]
