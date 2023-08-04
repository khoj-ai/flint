# Created manually by @sabaimran on 2023-08-03 00:52 AM baesd on https://github.com/pgvector/pgvector-python/tree/e6ca2c27c6a6fa8c183eea675fb8c8593403bad6

from django.db import migrations
from pgvector.django import VectorExtension

class Migration(migrations.Migration):

    operations = [
        VectorExtension()
    ]