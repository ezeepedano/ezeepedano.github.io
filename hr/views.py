from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
    employees = Employee.objects.filter(user=request.user)
    return render(request, 'hr/employee_list.html', {'employees': employees})

@login_required
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.user = request.user
            employee.save()
            messages.success(request, 'Employee created successfully.')
            return redirect('employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'hr/employee_form.html', {'form': form, 'title': 'New Employee'})

@login_required
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk, user=request.user)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Employee updated successfully.')
            return redirect('employee_list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'hr/employee_form.html', {'form': form, 'title': 'Edit Employee'})

@login_required
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk, user=request.user)
    if request.method == 'POST':
        employee.delete()
        messages.success(request, 'Employee deleted.')
        return redirect('employee_list')
    return render(request, 'hr/employee_confirm_delete.html', {'employee': employee})

@login_required
def payroll_list(request):
    # Filter by user via employee__user
    payrolls = Payroll.objects.filter(employee__user=request.user).order_by('-period', 'employee__last_name')
    return render(request, 'hr/payroll_list.html', {'payrolls': payrolls})

@login_required
def payroll_generate(request):
    if request.method == 'POST':
        form = PayrollGeneratonForm(request.user, request.POST)
        if form.is_valid():
            employee = form.cleaned_data['employee']
            period = form.cleaned_data['period']
            
            # Create Payroll
            # Check if exists?
            if Payroll.objects.filter(employee=employee, period__year=period.year, period__month=period.month).exists():
                 messages.error(request, f'Payroll for {employee} in {period.strftime("%m/%Y")} already exists.')
                 return redirect('payroll_list')
            
            payroll = Payroll(
                employee=employee,
                period=period,
                basic_salary=employee.basic_salary
            )
            payroll.save() # calculate_net called on save
            
            messages.success(request, f'Payroll generated for {employee}')
            return redirect('payroll_list')
    else:
        form = PayrollGeneratonForm(user=request.user)
        
    return render(request, 'hr/payroll_generate.html', {'form': form})

@login_required
def payroll_pay(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk, employee__user=request.user)
    
    if request.method == 'POST':
        if payroll.paid:
             messages.warning(request, 'This payroll is already paid.')
             return redirect('payroll_list')
             
        if payroll.paid:
             messages.warning(request, 'This payroll is already paid.')
             return redirect('payroll_list')
             
        account_id = request.POST.get('account')
        account = get_object_or_404(Account, pk=account_id, user=request.user)

        
        # 1. Update Payroll
        payroll.paid = True
        payroll.payment_date = timezone.now().date()
        payroll.save()
        
        # 2. Create Finance Movement
        CashMovement.objects.create(
            user=request.user,
            amount=payroll.net_salary,
            type='OUT',
            category='PAYROLL',
            account=account,
            description=f"Sueldo {payroll.employee} - {payroll.period.strftime('%m/%Y')}",
            date=timezone.now()
        )
        
        messages.success(request, f'Payroll marked as paid and recorded in Finance ({account.name}).')
        return redirect('payroll_list')
    
    accounts = Account.objects.filter(user=request.user, is_active=True)
    return render(request, 'hr/payroll_pay.html', {'payroll': payroll, 'accounts': accounts})
