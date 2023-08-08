def init_django():
    import os

    import django
    from django.conf import settings

    if settings.configured:
        return

    settings.configure(
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            'flint.db',
        ],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': os.environ.get("POSTGRES_DB", "postgres"),
                'USER': os.environ.get("POSTGRES_USER", "postgres"),
                'PASSWORD': os.environ.get("POSTGRES_PASSWORD", "postgres"),
                'HOST': os.environ.get("POSTGRES_HOST", "localhost"),
                'PORT': '5432',
            }
        },
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
    )

    django.setup()

if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    init_django()
    execute_from_command_line()