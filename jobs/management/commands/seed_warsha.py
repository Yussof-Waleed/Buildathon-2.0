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

        label_data = [
            ('ضوضاء المحرك', 'Engine noise'),
            ('فرامل', 'Brakes'),
            ('شبرا', 'Shubra'),
        ]
        labels = {}
        for title_ar, title_en in label_data:
            label, _ = Label.objects.update_or_create(
                title_en=title_en,
                defaults={'title_ar': title_ar},
            )
            labels[title_en] = label

        engine, _ = Diagnostic.objects.update_or_create(
            title_en='Engine noise check',
            defaults={
                'title_ar': 'فحص ضوضاء المحرك',
                'price': Decimal('800.00'),
            },
        )
        if engine.steps.count() == 0:
            DiagnosticStep.objects.bulk_create([
                DiagnosticStep(
                    diagnostic=engine,
                    title_ar='الاستماع والتشخيص',
                    title_en='Listen and diagnose',
                    description_ar='مراجعة التسجيل وتأكيد العطل.',
                    description_en='Review recording and confirm fault.',
                    expected_minutes=15,
                    sort_order=0,
                ),
                DiagnosticStep(
                    diagnostic=engine,
                    title_ar='استبدال السير البالي',
                    title_en='Replace worn belt',
                    description_ar='إزالة السير القديم وتركيب قطعة أصلية.',
                    description_en='Remove old belt, install new OEM part.',
                    expected_minutes=90,
                    sort_order=1,
                ),
                DiagnosticStep(
                    diagnostic=engine,
                    title_ar='تجربة قيادة',
                    title_en='Test drive',
                    description_ar='التأكد من اختفاء الضوضاء.',
                    description_en='Confirm noise is gone.',
                    expected_minutes=15,
                    sort_order=2,
                ),
            ])

        brakes, _ = Diagnostic.objects.update_or_create(
            title_en='Brake pads replacement',
            defaults={
                'title_ar': 'تغيير تيل الفرامل',
                'price': Decimal('1200.00'),
            },
        )
        if brakes.steps.count() == 0:
            DiagnosticStep.objects.bulk_create([
                DiagnosticStep(
                    diagnostic=brakes,
                    title_ar='فحص الفرامل',
                    title_en='Inspect brakes',
                    description_ar='فحص التيل والأقراص.',
                    description_en='Check pads and rotors.',
                    expected_minutes=20,
                    sort_order=0,
                ),
                DiagnosticStep(
                    diagnostic=brakes,
                    title_ar='استبدال التيل',
                    title_en='Replace pads',
                    description_ar='استبدال تيل الفرامل الأمامي.',
                    description_en='Front pad replacement.',
                    expected_minutes=60,
                    sort_order=1,
                ),
            ])

        self.stdout.write(self.style.SUCCESS(
            f'Seed complete: {len(labels)} labels, {Diagnostic.objects.count()} diagnostics'
        ))
