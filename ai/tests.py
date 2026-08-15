from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from ai.llm import LLMNotConfiguredError
from ai.tagger import suggest, TaggerResult
from catalog.models import Diagnostic, Label


class TaggerSuggestTests(TestCase):
    def setUp(self):
        self.engine_label = Label.objects.create(
            title_ar='ضوضاء المحرك',
            title_en='Engine noise',
        )
        self.brake_label = Label.objects.create(
            title_ar='فرامل',
            title_en='Brakes',
        )
        self.engine = Diagnostic.objects.create(
            title_ar='إصلاح ضوضاء سير المحرك',
            title_en='Engine belt / noise repair',
            price=Decimal('950.00'),
        )
        self.brakes = Diagnostic.objects.create(
            title_ar='تغيير تيل الفرامل الأمامي',
            title_en='Front brake pads',
            price=Decimal('1400.00'),
        )
        self.labels = list(Label.objects.values('id', 'title_ar', 'title_en'))
        self.diagnostics = list(
            Diagnostic.objects.values('id', 'title_ar', 'title_en', 'price'),
        )

    def test_json_returns_valid_ids(self):
        with patch(
            'ai.tagger.complete_json',
            return_value={
                'label_ids': [self.engine_label.pk, self.brake_label.pk],
                'diagnostic_id': self.engine.pk,
            },
        ):
            result = suggest('anything', self.labels, self.diagnostics)
        self.assertEqual(
            result.label_ids,
            [self.engine_label.pk, self.brake_label.pk],
        )
        self.assertEqual(result.diagnostic_id, self.engine.pk)

    def test_json_rejects_unknown_ids(self):
        with patch(
            'ai.tagger.complete_json',
            return_value={
                'label_ids': [self.engine_label.pk, 99999],
                'diagnostic_id': 88888,
            },
        ):
            result = suggest(
                'المحرك بيعمل صوت غريب',
                self.labels,
                self.diagnostics,
            )
        self.assertEqual(result.label_ids, [self.engine_label.pk])
        self.assertEqual(result.diagnostic_id, self.engine.pk)

    def test_keyword_fallback_when_groq_off(self):
        with patch(
            'ai.tagger.complete_json',
            side_effect=LLMNotConfiguredError('missing key'),
        ):
            result = suggest(
                'المحرك بيعمل صوت',
                self.labels,
                self.diagnostics,
            )
        self.assertEqual(result.label_ids, [self.engine_label.pk])
        self.assertEqual(result.diagnostic_id, self.engine.pk)
        self.assertIsInstance(result, TaggerResult)
