import importlib
mods = ['src.sales_domain_cleaner','src.logistics_domain_cleaner']
for m in mods:
    importlib.import_module(m)
print('imports ok')
