from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Diagnostic, DiagnosticStep, Label


LABELS = [
    ('ضوضاء المحرك', 'Engine noise'),
    ('فرامل', 'Brakes'),
    ('تغيير الزيت', 'Oil change'),
    ('البطارية', 'Battery'),
    ('التكييف', 'AC'),
    ('كهرباء', 'Electrical'),
    ('حرارة المحرك', 'Overheating'),
    ('عفشة', 'Suspension'),
    ('الكلاتش', 'Clutch'),
    ('كشف عام', 'Inspection'),
]

# title_en, title_ar, price, former title_en keys to migrate, steps
DIAGNOSTICS = [
    (
        'General inspection',
        'كشف عام',
        Decimal('250.00'),
        (),
        [
            {
                'title_ar': 'كشف بصري',
                'title_en': 'Visual check',
                'description_ar': 'مراجعة المحرك والفرامل والعفشة من برة.',
                'description_en': 'Walk-around of engine, brakes, and suspension.',
                'expected_minutes': 20,
            },
            {
                'title_ar': 'تقرير شفهي',
                'title_en': 'Verbal report',
                'description_ar': 'نقول للعميل اللي محتاج يتصلح.',
                'description_en': 'Tell the customer what needs work.',
                'expected_minutes': 10,
            },
        ],
    ),
    (
        'Engine belt / noise repair',
        'إصلاح ضوضاء سير المحرك',
        Decimal('950.00'),
        ('Engine noise check',),
        [
            {
                'title_ar': 'الاستماع والتشخيص',
                'title_en': 'Listen and diagnose',
                'description_ar': 'مراجعة التسجيل وتأكيد العطل.',
                'description_en': 'Review recording and confirm fault.',
                'expected_minutes': 15,
            },
            {
                'title_ar': 'استبدال السير البالي',
                'title_en': 'Replace worn belt',
                'description_ar': 'إزالة السير القديم وتركيب قطعة أصلية.',
                'description_en': 'Remove old belt, install new OEM part.',
                'expected_minutes': 90,
            },
            {
                'title_ar': 'تجربة قيادة',
                'title_en': 'Test drive',
                'description_ar': 'التأكد من اختفاء الضوضاء.',
                'description_en': 'Confirm noise is gone.',
                'expected_minutes': 15,
            },
        ],
    ),
    (
        'Front brake pads',
        'تغيير تيل الفرامل الأمامي',
        Decimal('1400.00'),
        ('Brake pads replacement',),
        [
            {
                'title_ar': 'فحص الفرامل',
                'title_en': 'Inspect brakes',
                'description_ar': 'فحص التيل والأقراص.',
                'description_en': 'Check pads and rotors.',
                'expected_minutes': 20,
            },
            {
                'title_ar': 'استبدال التيل',
                'title_en': 'Replace pads',
                'description_ar': 'استبدال تيل الفرامل الأمامي.',
                'description_en': 'Front pad replacement.',
                'expected_minutes': 60,
            },
            {
                'title_ar': 'تجربة فرامل',
                'title_en': 'Road test',
                'description_ar': 'التأكد إن الفرامل ماسكة كويس.',
                'description_en': 'Confirm the brakes bite cleanly.',
                'expected_minutes': 10,
            },
        ],
    ),
    (
        'Oil and filter change',
        'تغيير الزيت والفلتر',
        Decimal('750.00'),
        (),
        [
            {
                'title_ar': 'تفريغ الزيت القديم',
                'title_en': 'Drain old oil',
                'description_ar': 'تصفية الزيت المستعمل.',
                'description_en': 'Drain used engine oil.',
                'expected_minutes': 15,
            },
            {
                'title_ar': 'تغيير الفلتر والتعبئة',
                'title_en': 'Replace filter and refill',
                'description_ar': 'فلتر جديد وزيت مناسب للعربية.',
                'description_en': 'Fit a new filter and refill with the right grade.',
                'expected_minutes': 25,
            },
        ],
    ),
    (
        'Battery replacement',
        'تغيير البطارية',
        Decimal('2200.00'),
        (),
        [
            {
                'title_ar': 'فحص الشحن',
                'title_en': 'Test charging',
                'description_ar': 'قياس البطارية والدينامو.',
                'description_en': 'Measure battery and alternator.',
                'expected_minutes': 15,
            },
            {
                'title_ar': 'استبدال البطارية',
                'title_en': 'Replace battery',
                'description_ar': 'تركيب بطارية جديدة وتثبيت الأطراف.',
                'description_en': 'Fit a new battery and tighten terminals.',
                'expected_minutes': 20,
            },
        ],
    ),
    (
        'AC gas recharge',
        'تعبئة فريون التكييف',
        Decimal('550.00'),
        (),
        [
            {
                'title_ar': 'كشف تسريب',
                'title_en': 'Leak check',
                'description_ar': 'التأكد إن الدورة ما فيها تسريب.',
                'description_en': 'Confirm the circuit is not leaking.',
                'expected_minutes': 20,
            },
            {
                'title_ar': 'تعبئة الفريون',
                'title_en': 'Recharge gas',
                'description_ar': 'تعبئة الفريون وتجربة التبريد.',
                'description_en': 'Recharge and test cabin cooling.',
                'expected_minutes': 25,
            },
        ],
    ),
    (
        'Spark plugs',
        'تغيير البوجيهات',
        Decimal('650.00'),
        (),
        [
            {
                'title_ar': 'فك البوجيهات القديمة',
                'title_en': 'Remove old plugs',
                'description_ar': 'فك البوجيهات البالية.',
                'description_en': 'Remove worn spark plugs.',
                'expected_minutes': 20,
            },
            {
                'title_ar': 'تركيب بوجيهات جديدة',
                'title_en': 'Fit new plugs',
                'description_ar': 'تركيب بوجيهات جديدة وتجربة التعتيلة.',
                'description_en': 'Fit new plugs and check idle.',
                'expected_minutes': 20,
            },
        ],
    ),
    (
        'Coolant / overheating',
        'علاج حرارة المحرك',
        Decimal('1100.00'),
        (),
        [
            {
                'title_ar': 'فحص دورة التبريد',
                'title_en': 'Inspect cooling system',
                'description_ar': 'كشف الريداتير والخراطيم والليكات.',
                'description_en': 'Check radiator, hoses, and leaks.',
                'expected_minutes': 25,
            },
            {
                'title_ar': 'غسيل وتعبئة',
                'title_en': 'Flush and refill',
                'description_ar': 'غسيل الدورة وتعبئة مياه جديدة.',
                'description_en': 'Flush the system and refill coolant.',
                'expected_minutes': 40,
            },
            {
                'title_ar': 'تجربة حرارة',
                'title_en': 'Heat test',
                'description_ar': 'تشغيل العربية والتأكد إن الحرارة ثابتة.',
                'description_en': 'Run the engine and confirm temperature holds.',
                'expected_minutes': 15,
            },
        ],
    ),
    (
        'Front shocks (pair)',
        'تغيير مساعدين أمامي',
        Decimal('2800.00'),
        (),
        [
            {
                'title_ar': 'فحص العفشة',
                'title_en': 'Inspect suspension',
                'description_ar': 'كشف المساعدين والأذرعة.',
                'description_en': 'Check shocks and arms.',
                'expected_minutes': 20,
            },
            {
                'title_ar': 'استبدال المساعدين',
                'title_en': 'Replace shocks',
                'description_ar': 'تغيير المساعدين الأماميين.',
                'description_en': 'Replace the front pair.',
                'expected_minutes': 90,
            },
            {
                'title_ar': 'تجربة نطّة',
                'title_en': 'Bounce test',
                'description_ar': 'التأكد إن العربية واقفة مظبوط.',
                'description_en': 'Confirm the car sits and settles cleanly.',
                'expected_minutes': 10,
            },
        ],
    ),
    (
        'Clutch kit',
        'تغيير طقم الكلاتش',
        Decimal('5500.00'),
        (),
        [
            {
                'title_ar': 'فحص الكلاتش',
                'title_en': 'Inspect clutch',
                'description_ar': 'تجربة الدواسة والتأكد من التأكل.',
                'description_en': 'Check pedal feel and wear.',
                'expected_minutes': 20,
            },
            {
                'title_ar': 'استبدال الطقم',
                'title_en': 'Replace kit',
                'description_ar': 'تغيير القرص والصينية والبيرنج.',
                'description_en': 'Replace disc, cover, and release bearing.',
                'expected_minutes': 180,
            },
            {
                'title_ar': 'تجربة قيادة',
                'title_en': 'Test drive',
                'description_ar': 'التأكد إن التعشيق ناعم.',
                'description_en': 'Confirm smooth engagement.',
                'expected_minutes': 15,
            },
        ],
    ),
]


def _upsert_diagnostic(title_en, title_ar, price, former_titles, steps):
    diagnostic = Diagnostic.objects.filter(title_en=title_en).first()
    if diagnostic is None:
        for former in former_titles:
            diagnostic = Diagnostic.objects.filter(title_en=former).first()
            if diagnostic:
                break
    if diagnostic is None:
        diagnostic = Diagnostic(title_en=title_en)
    diagnostic.title_en = title_en
    diagnostic.title_ar = title_ar
    diagnostic.price = price
    diagnostic.save()

    diagnostic.steps.all().delete()
    DiagnosticStep.objects.bulk_create([
        DiagnosticStep(
            diagnostic=diagnostic,
            title_ar=step['title_ar'],
            title_en=step['title_en'],
            description_ar=step['description_ar'],
            description_en=step['description_en'],
            expected_minutes=step['expected_minutes'],
            sort_order=index,
        )
        for index, step in enumerate(steps)
    ])
    return diagnostic


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

        for title_ar, title_en in LABELS:
            Label.objects.update_or_create(
                title_en=title_en,
                defaults={'title_ar': title_ar},
            )
        removed, _ = Label.objects.filter(title_en='Shubra').delete()
        if removed:
            self.stdout.write('Removed neighbourhood-only label: Shubra')

        for title_en, title_ar, price, former_titles, steps in DIAGNOSTICS:
            _upsert_diagnostic(title_en, title_ar, price, former_titles, steps)

        self.stdout.write(self.style.SUCCESS(
            f'Seed complete: {Label.objects.count()} labels, '
            f'{Diagnostic.objects.count()} diagnostics'
        ))
