from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Employee(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) # Owner of the record (admin/manager)
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, unique=True)
    cuil = models.CharField(max_length=20, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    position = models.CharField(max_length=100, help_text="Cargo o Puesto")
    hire_date = models.DateField(default=timezone.now)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, help_text="Sueldo Básico Bruto")
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.last_name}, {self.first_name}"

class Payroll(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls')
    period = models.DateField(help_text="Fecha representativa del mes (ej: 01/11/2025 para Noviembre)")
    
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Deductions (Retenciones)
    retirement = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Jubilación (11%)")
    social_security = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Obra Social (3%)")
    pami = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Ley 19032 (3%)")
    
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Sueldo Neto a Pagar")
    
    paid = models.BooleanField(default=False)
    payment_date = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_net(self):
        # Auto-calculate standard argentinian deductions if basic_salary is set
        if self.basic_salary:
            self.retirement = self.basic_salary * 0.11
            self.social_security = self.basic_salary * 0.03
            self.pami = self.basic_salary * 0.03
            
        total_deductions = float(self.retirement) + float(self.social_security) + float(self.pami) + float(self.other_deductions)
        self.net_salary = float(self.basic_salary) - total_deductions

    def save(self, *args, **kwargs):
        if not self.id: # On create
             self.calculate_net()
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"Payroll {self.employee} - {self.period.strftime('%m/%Y')}"
