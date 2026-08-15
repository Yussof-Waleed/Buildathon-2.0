# Generated manually for bilingual order snapshot fields

from django.db import migrations, models


def copy_order_titles(apps, schema_editor):
    Order = apps.get_model('jobs', 'Order')
    OrderStep = apps.get_model('jobs', 'OrderStep')
    Diagnostic = apps.get_model('catalog', 'Diagnostic')

    for order in Order.objects.all():
        if order.diagnostic_id:
            diagnostic = Diagnostic.objects.filter(pk=order.diagnostic_id).first()
            if diagnostic:
                order.quoted_title_ar = diagnostic.title_ar
                order.quoted_title_en = diagnostic.title_en
                order.save(update_fields=['quoted_title_ar', 'quoted_title_en'])

    for step in OrderStep.objects.all():
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
        ('catalog', '0002_bilingual_titles'),
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='quoted_title_ar',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='order',
            name='quoted_title_en',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='orderstep',
            name='title_ar',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='orderstep',
            name='title_en',
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='orderstep',
            name='description_ar',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='orderstep',
            name='description_en',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(copy_order_titles, migrations.RunPython.noop),
        migrations.RemoveField(model_name='orderstep', name='title'),
        migrations.RemoveField(model_name='orderstep', name='description'),
        migrations.AlterField(
            model_name='orderstep',
            name='title_ar',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='orderstep',
            name='title_en',
            field=models.CharField(max_length=200),
        ),
    ]
