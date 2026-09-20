#!/usr/bin/env bash

set -o errexit

python manage.py collectstatic --no-input

python manage.py migrate

python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()

username = os.getenv("DJANGO_SUPERUSER_USERNAME")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

if username and password:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    if created:
        user.set_password(password)
        user.save()
        print("Superuser created successfully.")
    else:
        print("Superuser already exists.")
else:
    print("Superuser environment variables are not set.")
PY