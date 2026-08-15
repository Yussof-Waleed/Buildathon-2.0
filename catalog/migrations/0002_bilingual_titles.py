# Generated manually for bilingual catalog fields

from django.db import migrations, models


def copy_catalog_titles(apps, schema_editor):
    Label = apps.get_model('catalog', 'Label')
    for label in Label.objects.all():
        name = getattr(label, 'name', '') or ''
        label.title_en = name
        label.title_ar = name
        label.save(update_fields=['title_en', 'title_ar'])

    Diagnostic = apps.get_model('catalog', 'Diagnostic')
    for diagnostic in Diagnostic.objects.all():
        name = getattr(diagnostic, 'name', '') or ''
        diagnostic.title_en = name
        diagnostic.title_ar = name
        diagnostic.save(update_fields=['title_en', 'title_ar'])

    DiagnosticStep = apps.get_model('catalog', 'DiagnosticStep')
    for step in DiagnosticStep.objects.all():
        title = getattr(step, 'title', '') or ''
        description = getattr(step, 'description', '') or ''
        step.title_en = title
        step.title_ar = title
        step.description_en = description
        step.description_ar = description
        step.save(update_fields=[
            'title_en', 'title_ar', 'description_en', 'description_ar',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='label',
            name='title_ar',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='label',
            name='title_en',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='diagnostic',
            name='title_ar',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='diagnostic',
            name='title_en',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='diagnosticstep',
            name='title_ar',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='diagnosticstep',
            name='title_en',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='diagnosticstep',
            name='description_ar',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='diagnosticstep',
            name='description_en',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(copy_catalog_titles, migrations.RunPython.noop),
        migrations.RemoveField(model_name='label', name='name'),
        migrations.RemoveField(model_name='diagnostic', name='name'),
        migrations.RemoveField(model_name='diagnosticstep', name='title'),
        migrations.RemoveField(model_name='diagnosticstep', name='description'),
        migrations.AlterField(
            model_name='label',
            name='title_ar',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='label',
            name='title_en',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='diagnostic',
            name='title_ar',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='diagnostic',
            name='title_en',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='diagnosticstep',
            name='title_ar',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='diagnosticstep',
            name='title_en',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterModelOptions(
            name='diagnostic',
            options={'ordering': ['title_ar']},
        ),
        migrations.AlterModelOptions(
            name='label',
            options={'ordering': ['title_ar']},
        ),
    ]
