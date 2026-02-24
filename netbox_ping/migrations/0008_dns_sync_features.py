from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ipam', '0001_initial'),
        ('netbox_ping', '0007_pluginsettings_ping_timeout'),
    ]

    operations = [
        migrations.AddField(
            model_name='pluginsettings',
            name='dns_sync_to_netbox',
            field=models.BooleanField(
                default=False,
                help_text='Write resolved DNS names back to the built-in IPAddress dns_name field',
                verbose_name='Sync DNS to NetBox',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='dns_clear_on_missing',
            field=models.BooleanField(
                default=False,
                help_text='Clear IPAddress dns_name when reverse DNS returns empty',
                verbose_name='Clear DNS on Missing',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='dns_preserve_if_alive',
            field=models.BooleanField(
                default=True,
                help_text='Keep existing DNS name if host is alive but DNS lookup fails (overrides clear)',
                verbose_name='Preserve DNS if Alive',
            ),
        ),
        migrations.CreateModel(
            name='DnsHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('old_dns_name', models.CharField(blank=True, default='', max_length=255)),
                ('new_dns_name', models.CharField(blank=True, default='', max_length=255)),
                ('changed_at', models.DateTimeField()),
                ('ip_address', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dns_history',
                    to='ipam.ipaddress',
                )),
            ],
            options={
                'verbose_name': 'DNS History',
                'verbose_name_plural': 'DNS History',
                'ordering': ['-changed_at'],
                'indexes': [
                    models.Index(fields=['ip_address', '-changed_at'], name='netbox_ping_ip_address_c85a9e_idx'),
                ],
            },
        ),
    ]
