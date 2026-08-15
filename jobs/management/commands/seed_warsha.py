from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Diagnostic, DiagnosticStep, Label


class Command(BaseCommand):
    help = 'Seed Warsha demo data: Kareem staff user, labels, diagnostics.'

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()

        kareem, created = user_model.objects.get_or_create(
            username='kareem',
            defaults={
                'email': 'kareem@warsha.local',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            kareem.set_password('warsha2026')
            kareem.save()
            self.stdout.write(self.style.SUCCESS('Created Kareem user (kareem / warsha2026)'))
        else:
            self.stdout.write('Kareem user already exists')

        labels = {}
        for name in ('Engine noise', 'Brakes', 'Shubra'):
            label, _ = Label.objects.get_or_create(name=name)
            labels[name] = label

        engine, _ = Diagnostic.objects.get_or_create(
            name='Engine noise check',
            defaults={'price': Decimal('800.00')},
        )
        if engine.steps.count() == 0:
            DiagnosticStep.objects.bulk_create([
                DiagnosticStep(
                    diagnostic=engine,
                    title='Listen and diagnose',
                    description='Review recording and confirm fault.',
                    expected_minutes=15,
                    sort_order=0,
                ),
                DiagnosticStep(
                    diagnostic=engine,
                    title='Replace worn belt',
                    description='Remove old belt, install new OEM part.',
                    expected_minutes=90,
                    sort_order=1,
                ),
                DiagnosticStep(
                    diagnostic=engine,
                    title='Test drive',
                    description='Confirm noise is gone.',
                    expected_minutes=15,
                    sort_order=2,
                ),
            ])

        brakes, _ = Diagnostic.objects.get_or_create(
            name='Brake pads replacement',
            defaults={'price': Decimal('1200.00')},
        )
        if brakes.steps.count() == 0:
            DiagnosticStep.objects.bulk_create([
                DiagnosticStep(
                    diagnostic=brakes,
                    title='Inspect brakes',
                    description='Check pads and rotors.',
                    expected_minutes=20,
                    sort_order=0,
                ),
                DiagnosticStep(
                    diagnostic=brakes,
                    title='Replace pads',
                    description='Front pad replacement.',
                    expected_minutes=60,
                    sort_order=1,
                ),
            ])

        self.stdout.write(self.style.SUCCESS(
            f'Seed complete: {len(labels)} labels, {Diagnostic.objects.count()} diagnostics'
        ))
