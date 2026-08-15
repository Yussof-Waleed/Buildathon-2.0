from django.db import migrations, models
import django.db.models.deletion


def collapse_duplicate_order_conversations(apps, schema_editor):
    Conversation = apps.get_model('jobs', 'Conversation')
    seen = {}
    for conversation in Conversation.objects.exclude(order_id=None).order_by('id'):
        order_id = conversation.order_id
        if order_id in seen:
            conversation.order_id = None
            conversation.save(update_fields=['order_id'])
        else:
            seen[order_id] = conversation.pk


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_bilingual_titles'),
    ]

    operations = [
        migrations.RunPython(
            collapse_duplicate_order_conversations,
            migrations.RunPython.noop,
        ),
        migrations.AddField(
            model_name='conversation',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                help_text='Set when this chat was forked from another order chat.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children',
                to='jobs.conversation',
            ),
        ),
        migrations.AlterField(
            model_name='conversation',
            name='order',
            field=models.ForeignKey(
                blank=True,
                help_text='Null = intake not yet bound to an order. One dedicated chat per order.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversations',
                to='jobs.order',
                unique=True,
            ),
        ),
    ]
