from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from catalog.forms import DiagnosticForm, DiagnosticStepFormSet, LabelForm
from catalog.models import Diagnostic, Label
from jobs.kareem_views import staff_required
from jobs.models import Order


@staff_required
def kareem_diagnostics_list(request):
    diagnostics = Diagnostic.objects.annotate(
        step_count=Count('steps'),
        order_count=Count('orders'),
    ).order_by('name')

    return render(
        request,
        'mechanic/diagnostics_list.html',
        {
            'nav_active': 'diagnostics',
            'diagnostics': diagnostics,
        },
    )


@staff_required
def kareem_diagnostic_create(request):
    if request.method == 'POST':
        form = DiagnosticForm(request.POST)
        if form.is_valid():
            diagnostic = form.save()
            formset = DiagnosticStepFormSet(request.POST, instance=diagnostic)
            if formset.is_valid():
                formset.save()
                messages.success(request, 'تم إنشاء التشخيص.')
                return redirect('kareem-diagnostics-list')
        else:
            diagnostic = Diagnostic()
            formset = DiagnosticStepFormSet(request.POST, instance=diagnostic)
    else:
        diagnostic = Diagnostic()
        form = DiagnosticForm()
        formset = DiagnosticStepFormSet(instance=diagnostic)

    return render(
        request,
        'mechanic/diagnostic_form.html',
        {
            'nav_active': 'diagnostics',
            'form': form,
            'formset': formset,
            'is_edit': False,
        },
    )


@staff_required
def kareem_diagnostic_edit(request, diagnostic_id):
    diagnostic = get_object_or_404(Diagnostic, pk=diagnostic_id)

    if request.method == 'POST':
        form = DiagnosticForm(request.POST, instance=diagnostic)
        formset = DiagnosticStepFormSet(request.POST, instance=diagnostic)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'تم تحديث التشخيص.')
            return redirect('kareem-diagnostics-list')
    else:
        form = DiagnosticForm(instance=diagnostic)
        formset = DiagnosticStepFormSet(instance=diagnostic)

    return render(
        request,
        'mechanic/diagnostic_form.html',
        {
            'nav_active': 'diagnostics',
            'form': form,
            'formset': formset,
            'diagnostic': diagnostic,
            'is_edit': True,
        },
    )


@staff_required
def kareem_diagnostic_delete(request, diagnostic_id):
    if request.method != 'POST':
        return redirect('kareem-diagnostics-list')

    diagnostic = get_object_or_404(Diagnostic, pk=diagnostic_id)
    if Order.objects.filter(diagnostic=diagnostic).exists():
        messages.error(request, 'لا يمكن حذف تشخيص مرتبط بطلبات.')
        return redirect('kareem-diagnostics-list')

    diagnostic.delete()
    messages.success(request, 'تم حذف التشخيص.')
    return redirect('kareem-diagnostics-list')


@staff_required
def kareem_labels_list(request):
    labels = Label.objects.annotate(order_count=Count('orders')).order_by('name')

    if request.method == 'POST' and request.POST.get('action') == 'create':
        form = LabelForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الوسم.')
            return redirect('kareem-labels-list')
    else:
        form = LabelForm()

    return render(
        request,
        'mechanic/labels_list.html',
        {
            'nav_active': 'labels',
            'labels': labels,
            'form': form,
        },
    )


@staff_required
def kareem_label_edit(request, label_id):
    if request.method != 'POST':
        return redirect('kareem-labels-list')

    label = get_object_or_404(Label, pk=label_id)
    form = LabelForm(request.POST, instance=label)
    if form.is_valid():
        form.save()
        messages.success(request, 'تم تحديث الوسم.')
    else:
        messages.error(request, 'اسم الوسم غير صالح.')
    return redirect('kareem-labels-list')


@staff_required
def kareem_label_delete(request, label_id):
    if request.method != 'POST':
        return redirect('kareem-labels-list')

    label = get_object_or_404(Label, pk=label_id)
    if label.orders.exists():
        messages.error(request, 'لا يمكن حذف وسوم مرتبطة بطلبات.')
        return redirect('kareem-labels-list')

    label.delete()
    messages.success(request, 'تم حذف الوسم.')
    return redirect('kareem-labels-list')
