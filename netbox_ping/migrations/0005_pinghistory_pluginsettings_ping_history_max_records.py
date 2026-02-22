from django.db import migrations, models
import django.db.models.deletion
import taggit.managers
import utilities.json


class Migration(migrations.Migration):

    dependencies = [
        ('ipam', '0001_initial'),
        ('extras', '0001_initial'),
        ('netbox_ping', '0004_subnetscanresult_last_discovered'),
    ]

    operations = [
        migrations.CreateModel(
            name='PingHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('is_reachable', models.BooleanField()),
                ('response_time_ms', models.FloatField(blank=True, null=True)),
                ('dns_name', models.CharField(blank=True, default='', max_length=255)),
                ('checked_at', models.DateTimeField()),
                ('ip_address', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ping_history', to='ipam.ipaddress')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Ping History',
                'verbose_name_plural': 'Ping History',
                'ordering': ['-checked_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pinghistory',
            index=models.Index(fields=['ip_address', '-checked_at'], name='netbox_ping_ip_addr_b3f4e7_idx'),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='ping_history_max_records',
            field=models.IntegerField(default=50000, help_text='Maximum number of ping history records to keep (0 = unlimited)', verbose_name='Max Ping History Records'),
        ),
    ]
