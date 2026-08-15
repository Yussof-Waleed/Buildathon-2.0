from django import forms
from django.forms import inlineformset_factory

from catalog.models import Diagnostic, DiagnosticStep, Label


class LabelForm(forms.ModelForm):
    class Meta:
        model = Label
        fields = ('name',)
        widgets = {
            'name': forms.TextInput(attrs={
                'class': (
                    'w-full rounded-xl border border-white/10 bg-black/30 '
                    'px-4 py-3 text-paper focus:border-copper-bright focus:outline-none'
                ),
                'dir': 'auto',
            }),
        }


class DiagnosticForm(forms.ModelForm):
    class Meta:
        model = Diagnostic
        fields = ('name', 'price')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': (
                    'w-full rounded-xl border border-white/10 bg-black/30 '
                    'px-4 py-3 text-paper focus:border-copper-bright focus:outline-none'
                ),
                'dir': 'auto',
            }),
            'price': forms.NumberInput(attrs={
                'class': (
                    'w-full rounded-xl border border-white/10 bg-black/30 '
                    'px-4 py-3 text-paper focus:border-copper-bright focus:outline-none'
                ),
                'step': '0.01',
                'min': '0',
            }),
        }


class DiagnosticStepForm(forms.ModelForm):
    class Meta:
        model = DiagnosticStep
        fields = ('title', 'description', 'expected_minutes', 'sort_order')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': (
                    'w-full rounded-lg border border-white/10 bg-black/30 '
                    'px-3 py-2 text-sm text-paper focus:border-copper-bright focus:outline-none'
                ),
                'dir': 'auto',
            }),
            'description': forms.Textarea(attrs={
                'class': (
                    'w-full rounded-lg border border-white/10 bg-black/30 '
                    'px-3 py-2 text-sm text-paper focus:border-copper-bright focus:outline-none'
                ),
                'rows': 2,
                'dir': 'auto',
            }),
            'expected_minutes': forms.NumberInput(attrs={
                'class': (
                    'w-full rounded-lg border border-white/10 bg-black/30 '
                    'px-3 py-2 text-sm text-paper focus:border-copper-bright focus:outline-none'
                ),
                'min': '1',
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': (
                    'w-full rounded-lg border border-white/10 bg-black/30 '
                    'px-3 py-2 text-sm text-paper focus:border-copper-bright focus:outline-none'
                ),
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
