from django.contrib import admin

from catalog.models import Diagnostic, DiagnosticStep, Label


class DiagnosticStepInline(admin.TabularInline):
    model = DiagnosticStep
    extra = 1
    fields = (
        'title_ar',
        'title_en',
        'description_ar',
        'description_en',
        'expected_minutes',
        'sort_order',
    )


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('title_ar', 'title_en', 'created_at')
    search_fields = ('title_ar', 'title_en')


@admin.register(Diagnostic)
class DiagnosticAdmin(admin.ModelAdmin):
    list_display = ('title_ar', 'title_en', 'price', 'updated_at')
    search_fields = ('title_ar', 'title_en')
    inlines = [DiagnosticStepInline]
