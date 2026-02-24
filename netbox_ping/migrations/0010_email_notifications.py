import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ipam', '0001_initial'),
        ('netbox_ping', '0009_skip_reserved_ips'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScanEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('event_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('ip_went_down', 'IP Went Down'),
                        ('ip_came_up', 'IP Came Up'),
                        ('ip_discovered', 'IP Discovered'),
                        ('dns_changed', 'DNS Changed'),
                    ],
                )),
                ('detail', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('digest_sent', models.BooleanField(default=False)),
                ('prefix', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='+',
                    to='ipam.prefix',
                )),
                ('ip_address', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='+',
                    to='ipam.ipaddress',
                )),
            ],
            options={
                'verbose_name': 'Scan Event',
                'verbose_name_plural': 'Scan Events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='scanevent',
            index=models.Index(fields=['digest_sent', '-created_at'], name='netbox_ping_digest_sent_idx'),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='email_notifications_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Send periodic digest emails summarizing scan results and changes',
                verbose_name='Enable Email Notifications',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='email_recipients',
            field=models.TextField(
                blank=True, default='',
                help_text='Comma-separated email addresses to receive digest reports',
                verbose_name='Email Recipients',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='email_digest_interval',
            field=models.IntegerField(
                default=1440,
                choices=[
                    (0, 'Disabled'),
                    (60, 'Hourly'),
                    (360, 'Every 6 hours'),
                    (720, 'Every 12 hours'),
                    (1440, 'Daily'),
                    (10080, 'Weekly'),
                ],
                help_text='How often to send digest emails (0 = disabled)',
                verbose_name='Digest Interval',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='email_include_details',
            field=models.BooleanField(
                default=True,
                help_text='Include per-IP change tables in digest emails',
                verbose_name='Include Details',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='email_utilization_threshold',
            field=models.IntegerField(
                default=90,
                help_text='Include prefixes at or above this utilization in digests (0 = disabled)',
                verbose_name='Utilization Alert Threshold (%)',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='email_on_change_only',
            field=models.BooleanField(
                default=True,
                help_text='Skip sending digest if there are no events or high-utilization alerts',
                verbose_name='Send on Change Only',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='email_last_digest_sent',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Last Digest Sent',
            ),
        ),
    ]
