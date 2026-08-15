from django import forms
from django.forms import inlineformset_factory

from catalog.models import Diagnostic, DiagnosticStep, Label

INPUT_CLASS = (
    'w-full rounded-xl border border-white/10 bg-black/30 '
    'px-4 py-3 text-paper focus:border-copper-bright focus:outline-none'
)
STEP_INPUT_CLASS = (
    'w-full rounded-lg border border-white/10 bg-black/30 '
    'px-3 py-2 text-sm text-paper focus:border-copper-bright focus:outline-none'
)


class LabelForm(forms.ModelForm):
    class Meta:
        model = Label
        fields = ('title_ar', 'title_en')
        widgets = {
            'title_ar': forms.TextInput(attrs={'class': INPUT_CLASS, 'dir': 'rtl'}),
            'title_en': forms.TextInput(attrs={'class': INPUT_CLASS, 'dir': 'ltr'}),
        }


class DiagnosticForm(forms.ModelForm):
    class Meta:
        model = Diagnostic
        fields = ('title_ar', 'title_en', 'price')
        widgets = {
            'title_ar': forms.TextInput(attrs={'class': INPUT_CLASS, 'dir': 'rtl'}),
            'title_en': forms.TextInput(attrs={'class': INPUT_CLASS, 'dir': 'ltr'}),
            'price': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'step': '0.01',
                'min': '0',
            }),
        }


class DiagnosticStepForm(forms.ModelForm):
    class Meta:
        model = DiagnosticStep
        fields = (
            'title_ar',
            'title_en',
            'description_ar',
            'description_en',
            'expected_minutes',
            'sort_order',
        )
        widgets = {
            'title_ar': forms.TextInput(attrs={'class': STEP_INPUT_CLASS, 'dir': 'rtl'}),
            'title_en': forms.TextInput(attrs={'class': STEP_INPUT_CLASS, 'dir': 'ltr'}),
            'description_ar': forms.Textarea(attrs={
                'class': STEP_INPUT_CLASS,
                'rows': 2,
                'dir': 'rtl',
            }),
            'description_en': forms.Textarea(attrs={
                'class': STEP_INPUT_CLASS,
                'rows': 2,
                'dir': 'ltr',
            }),
            'expected_minutes': forms.NumberInput(attrs={
                'class': STEP_INPUT_CLASS,
                'min': '1',
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': STEP_INPUT_CLASS,
                'min': '0',
            }),
        }


DiagnosticStepFormSet = inlineformset_factory(
    Diagnostic,
    DiagnosticStep,
    form=DiagnosticStepForm,
    extra=2,
    can_delete=True,
)
