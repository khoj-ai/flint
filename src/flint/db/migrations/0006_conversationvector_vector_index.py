# Generated by Django 4.2.4 on 2023-09-11 17:01

from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0005_alter_conversationvector_vector"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="conversationvector",
            index=pgvector.django.IvfflatIndex(
                fields=["vector"], lists=100, name="vector_index", opclasses=["vector_cosine_ops"]
            ),
        ),
    ]
