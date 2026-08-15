from django.contrib import admin

from catalog.models import Diagnostic, DiagnosticStep, Label


class DiagnosticStepInline(admin.TabularInline):
    model = DiagnosticStep
    extra = 1
    fields = ('title', 'description', 'expected_minutes', 'sort_order')


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Diagnostic)
class DiagnosticAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'updated_at')
    search_fields = ('name',)
    inlines = [DiagnosticStepInline]
