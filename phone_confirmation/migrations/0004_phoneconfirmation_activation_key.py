# Generated by Django 2.1.3 on 2018-12-07 12:45

from django.db import migrations, models
import phone_confirmation.models


class Migration(migrations.Migration):

    dependencies = [
        ('phone_confirmation', '0003_phoneconfirmation_first_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='phoneconfirmation',
            name='activation_key',
            field=models.CharField(default=phone_confirmation.models.generate_token, max_length=256, unique=True),
        ),
    ]
