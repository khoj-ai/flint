# Generated by Django 4.2.4 on 2023-08-11 01:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("db", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="conversation",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
