from django.db import migrations


def normalize_skus(apps, schema_editor):
    Product = apps.get_model('inventory', 'Product')
    seen = {}  # (user_id, lowered_sku) -> first Product.pk
    for p in Product.objects.all().order_by('pk'):
        if not p.sku:
            continue
        lowered = p.sku.strip().lower()
        if lowered == p.sku:
            continue
        key = (p.user_id, lowered)
        existing_pk = seen.get(key)
        if existing_pk is None:
            existing = Product.objects.filter(user_id=p.user_id, sku=lowered).exclude(pk=p.pk).first()
            if existing:
                seen[key] = existing.pk
                p.sku = f"{lowered}__dup_{p.pk}"
            else:
                p.sku = lowered
                seen[key] = p.pk
        else:
            p.sku = f"{lowered}__dup_{p.pk}"
        p.save(update_fields=['sku'])


def noop_reverse(apps, schema_editor):
    # Lowercasing is not safely reversible.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0015_alter_product_weight_kg'),
    ]

    operations = [
        migrations.RunPython(normalize_skus, noop_reverse),
    ]
