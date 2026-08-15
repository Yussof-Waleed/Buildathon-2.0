from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0003_conversation_parent_unique_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversation',
            name='order',
            field=models.OneToOneField(
                blank=True,
                help_text='Null = intake not yet bound to an order. One dedicated chat per order.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversation',
                to='jobs.order',
            ),
        ),
    ]
