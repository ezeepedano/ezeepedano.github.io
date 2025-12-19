from django.db import migrations
from django.contrib.auth.hashers import make_password

def assign_data_to_test_user(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    # Inventory
    Category = apps.get_model('inventory', 'Category')
    Product = apps.get_model('inventory', 'Product')
    Ingredient = apps.get_model('inventory', 'Ingredient')
    Recipe = apps.get_model('inventory', 'Recipe')
    ProductionOrder = apps.get_model('inventory', 'ProductionOrder')
    # Sales
    Customer = apps.get_model('sales', 'Customer')
    Sale = apps.get_model('sales', 'Sale')
    # Finance
    FixedCost = apps.get_model('finance', 'FixedCost')
    MonthlyExpense = apps.get_model('finance', 'MonthlyExpense')
    Provider = apps.get_model('finance', 'Provider')
    PurchaseCategory = apps.get_model('finance', 'PurchaseCategory')
    Purchase = apps.get_model('finance', 'Purchase')

    # Create Test User
    test_user, created = User.objects.get_or_create(username='user', defaults={
        'email': 'test@example.com',
        'is_staff': True,
        'is_superuser': True
    })
    if created:
        test_user.password = make_password('test')
        test_user.save()
    else:
        # Ensure password is 'test' if user existed but we want to be sure
        # Only set if you are sure. User asked: "user de prueba el cual el usuario es user y la contraseña test"
        if not test_user.check_password('test'):
             test_user.password = make_password('test')
             test_user.save()

    # Assign Data
    print(f" Assigning data to user: {test_user.username}...")
    
    # Inventory
    Category.objects.update(user=test_user)
    Product.objects.update(user=test_user)
    Ingredient.objects.update(user=test_user)
    Recipe.objects.update(user=test_user)
    ProductionOrder.objects.update(user=test_user)
    
    # Sales
    Customer.objects.update(user=test_user)
    Sale.objects.update(user=test_user)

    # Finance
    FixedCost.objects.update(user=test_user)
    MonthlyExpense.objects.update(user=test_user)
    Provider.objects.update(user=test_user)
    PurchaseCategory.objects.update(user=test_user)
    Purchase.objects.update(user=test_user)

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_category_user_ingredient_user_product_user_and_more'),
        ('sales', '0003_customer_user_sale_user'),
        ('finance', '0004_fixedcost_user_monthlyexpense_user_provider_user_and_more'),
    ]

    operations = [
        migrations.RunPython(assign_data_to_test_user),
    ]
