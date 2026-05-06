from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from .models import Employee, Payroll
from django import forms
from django.utils import timezone
from finance.models import Account, CashMovement

# --- Forms ---
class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        exclude = ['user', 'created_at', 'updated_at']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
        }

class PayrollGeneratonForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=None)
    period = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), help_text="Select a date in the month you are paying")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(user=user, is_active=True)

# --- Views ---

@login_required
def employee_list(request):
    qs = Employee.objects.filter(user=request.user)

    search_query = (request.GET.get('q') or '').strip()
    filter_status = request.GET.get('status') or ''

    if search_query:
        qs = qs.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(dni__icontains=search_query)
            | Q(position__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    if filter_status == 'active':
        qs = qs.filter(is_active=True)
    elif filter_status == 'inactive':
        qs = qs.filter(is_active=False)

    qs = qs.order_by('last_name', 'first_name')

    base = Employee.objects.filter(user=request.user)
    kpi_total = base.count()
    kpi_active = base.filter(is_active=True).count()
    kpi_inactive = kpi_total - kpi_active
    kpi_monthly_cost = base.filter(is_active=True).aggregate(s=Sum('basic_salary'))['s'] or 0

    context = {
        'employees': qs,
        'search_query': search_query,
        'filter_status': filter_status,
        'kpi_total': kpi_total,
        'kpi_active': kpi_active,
        'kpi_inactive': kpi_inactive,
        'kpi_monthly_cost': kpi_monthly_cost,
    }
    return render(request, 'hr/employee_list.html', context)

@login_required
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.user = request.user
            employee.save()
            messages.success(request, 'Empleado creado correctamente.')
            return redirect('employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'hr/employee_form.html', {'form': form, 'title': 'Nuevo empleado'})

@login_required
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk, user=request.user)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empleado actualizado correctamente.')
            return redirect('employee_list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'hr/employee_form.html', {'form': form, 'title': 'Editar empleado', 'employee': employee})

@login_required
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk, user=request.user)
    if request.method == 'POST':
        employee.delete()
        messages.success(request, 'Empleado eliminado.')
        return redirect('employee_list')
    return render(request, 'hr/employee_confirm_delete.html', {'employee': employee})

@login_required
def payroll_list(request):
    qs = Payroll.objects.filter(employee__user=request.user).select_related('employee')

    filter_year = request.GET.get('year') or ''
    filter_month = request.GET.get('month') or ''
    filter_status = request.GET.get('status') or ''

    if filter_year:
        try:
            qs = qs.filter(period__year=int(filter_year))
        except (TypeError, ValueError):
            pass
    if filter_month:
        try:
            qs = qs.filter(period__month=int(filter_month))
        except (TypeError, ValueError):
            pass
    if filter_status == 'paid':
        qs = qs.filter(paid=True)
    elif filter_status == 'pending':
        qs = qs.filter(paid=False)

    qs = qs.order_by('-period', 'employee__last_name')

    base = Payroll.objects.filter(employee__user=request.user)
    kpi_total = base.count()
    kpi_paid = base.filter(paid=True).count()
    kpi_pending = base.filter(paid=False).count()
    kpi_amount_total = base.aggregate(s=Sum('net_salary'))['s'] or 0
    kpi_amount_paid = base.filter(paid=True).aggregate(s=Sum('net_salary'))['s'] or 0
    kpi_amount_pending = base.filter(paid=False).aggregate(s=Sum('net_salary'))['s'] or 0

    # Distinct years for the filter dropdown
    years = sorted({p.period.year for p in base.only('period')}, reverse=True)

    context = {
        'payrolls': qs,
        'filter_year': filter_year,
        'filter_month': filter_month,
        'filter_status': filter_status,
        'years': years,
        'kpi_total': kpi_total,
        'kpi_paid': kpi_paid,
        'kpi_pending': kpi_pending,
        'kpi_amount_total': kpi_amount_total,
        'kpi_amount_paid': kpi_amount_paid,
        'kpi_amount_pending': kpi_amount_pending,
    }
    return render(request, 'hr/payroll_list.html', context)

@login_required
def payroll_generate(request):
    if request.method == 'POST':
        form = PayrollGeneratonForm(request.user, request.POST)
        if form.is_valid():
            employee = form.cleaned_data['employee']
            period = form.cleaned_data['period']

            if Payroll.objects.filter(employee=employee, period__year=period.year, period__month=period.month).exists():
                 messages.error(request, f'Ya existe nómina para {employee} en {period.strftime("%m/%Y")}.')
                 return redirect('payroll_list')

            payroll = Payroll(
                employee=employee,
                period=period,
                basic_salary=employee.basic_salary
            )
            payroll.save()

            messages.success(request, f'Nómina generada para {employee}.')
            return redirect('payroll_list')
    else:
        form = PayrollGeneratonForm(user=request.user)

    employees = Employee.objects.filter(user=request.user, is_active=True).order_by('last_name')
    total_basic = employees.aggregate(s=Sum('basic_salary'))['s'] or 0

    return render(request, 'hr/payroll_generate.html', {
        'form': form,
        'employees': employees,
        'total_basic': total_basic,
    })

@login_required
def payroll_pay(request, pk):
    payroll = get_object_or_404(
        Payroll.objects.select_related('employee'),
        pk=pk, employee__user=request.user,
    )

    if request.method == 'POST':
        if payroll.paid:
             messages.warning(request, 'Esta nómina ya está pagada.')
             return redirect('payroll_list')

        account_id = request.POST.get('account')
        account = get_object_or_404(Account, pk=account_id, user=request.user)

        payroll.paid = True
        payroll.payment_date = timezone.now().date()
        payroll.save()

        CashMovement.objects.create(
            user=request.user,
            amount=payroll.net_salary,
            type='OUT',
            category='PAYROLL',
            account=account,
            description=f"Sueldo {payroll.employee} - {payroll.period.strftime('%m/%Y')}",
            date=timezone.now()
        )

        messages.success(request, f'Nómina marcada como pagada y registrada en {account.name}.')
        return redirect('payroll_list')

    accounts = Account.objects.filter(user=request.user, is_active=True)
    return render(request, 'hr/payroll_pay.html', {'payroll': payroll, 'accounts': accounts})
