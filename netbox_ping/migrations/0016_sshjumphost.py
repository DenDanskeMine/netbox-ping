import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0015_subnetscanresult_job_ids'),
    ]

    operations = [
        migrations.CreateModel(
            name='SSHJumpHost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('host', models.CharField(max_length=255)),
                ('port', models.IntegerField(default=22)),
                ('username', models.CharField(max_length=64)),
                ('key_file', models.CharField(help_text='Absolute path to private key on the NetBox host', max_length=512)),
                ('known_hosts_file', models.CharField(blank=True, help_text='Leave blank to skip host key checking', max_length=512)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='ssh_jumphost_enabled',
            field=models.BooleanField(default=False, verbose_name='Enable SSH Jumphost', help_text='Route pings through an SSH jumphost instead of pinging directly'),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='default_jumphost',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='netbox_ping.sshjumphost', verbose_name='Default Jumphost'),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='ssh_fallback_to_local',
            field=models.BooleanField(default=True, verbose_name='Fallback to Local', help_text='Fall back to local ping if SSH connection fails'),
        ),
        migrations.AddField(
            model_name='prefixschedule',
            name='ping_mode',
            field=models.CharField(
                choices=[('follow_global', 'Follow Global'), ('force_local', 'Force Local Ping'), ('force_ssh', 'Force SSH Jumphost')],
                default='follow_global',
                max_length=20,
                verbose_name='Ping Mode',
                help_text='Follow global jumphost setting, force local ping, or force a specific SSH jumphost',
            ),
        ),
        migrations.AddField(
            model_name='prefixschedule',
            name='custom_jumphost',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='netbox_ping.sshjumphost', help_text='Used when Ping Mode is Force SSH Jumphost'),
        ),
    ]
