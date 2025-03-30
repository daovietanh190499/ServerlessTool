# Generated by Django 5.1.5 on 2025-03-30 10:39

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Tool',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(blank=True, max_length=120, unique=True)),
                ('description', models.TextField(blank=True)),
                ('python_script', models.TextField(blank=True)),
                ('requirements', models.TextField(blank=True, help_text='Mỗi package trên một dòng')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('docker_image', models.CharField(blank=True, max_length=255)),
                ('is_built', models.BooleanField(default=False)),
                ('is_running', models.BooleanField(default=False)),
                ('build_status', models.CharField(default='not_built', max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='DeploymentLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('log', models.TextField()),
                ('status', models.CharField(max_length=50)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('tool', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deployment_logs', to='dashboard.tool')),
            ],
        ),
        migrations.CreateModel(
            name='BuildLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('log', models.TextField()),
                ('status', models.CharField(max_length=50)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('tool', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='build_logs', to='dashboard.tool')),
            ],
        ),
        migrations.CreateModel(
            name='EnvironmentVariable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100)),
                ('value', models.CharField(max_length=500)),
                ('is_secret', models.BooleanField(default=False)),
                ('tool', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='environment_variables', to='dashboard.tool')),
            ],
            options={
                'unique_together': {('tool', 'key')},
            },
        ),
        migrations.CreateModel(
            name='ToolDependency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dependent_tool', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dependent_tools', to='dashboard.tool')),
                ('tool', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dependencies', to='dashboard.tool')),
            ],
            options={
                'unique_together': {('tool', 'dependent_tool')},
            },
        ),
    ]
