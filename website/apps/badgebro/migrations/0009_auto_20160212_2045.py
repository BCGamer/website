# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('badgebro', '0008_auto_20160111_1949'),
    ]

    operations = [
        migrations.AddField(
            model_name='badge',
            name='collected',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='badge',
            name='printed',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
