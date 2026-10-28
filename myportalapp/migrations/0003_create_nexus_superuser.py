from django.db import migrations
from django.contrib.auth.hashers import make_password


def create_or_update_nexus_superuser(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    username = 'nexussuperuser'
    password = 'nexusadmin'
    email = 'admin@nexus.edu'

    user = User.objects.filter(username=username).first()
    if user:
        user.password = make_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()
    else:
        User.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )


def remove_nexus_superuser(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='nexussuperuser').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('myportalapp', '0002_certificate_signature_image_and_more'),
    ]

    operations = [
        migrations.RunPython(create_or_update_nexus_superuser, remove_nexus_superuser),
    ]
