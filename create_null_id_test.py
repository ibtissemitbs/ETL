#!/usr/bin/env python3
"""Test that ID columns don't get filled with 'Autre'"""
import pandas as pd

# Create test data with NULL in shipment_id
df = pd.DataFrame({
    'shipment_id': ['SH-001', None, 'SH-003', None, 'SH-005'],
    'origin': ['China', 'USA', 'France', 'Germany', 'Spain'],
    'destination': ['France', 'UK', 'Germany', 'Italy', 'Portugal'],
    'weight': [50.0, 60.0, 45.0, 55.0, 40.0],
    'shipping_cost': [100.0, 120.0, 95.0, 110.0, 85.0],
    'delivery_date': ['2024-01-10', '2024-01-15', '2024-01-12', '2024-01-18', '2024-01-20'],
    'status': ['Delivered', 'In Transit', 'Pending', 'Delivered', 'In Transit']
})

df.to_csv('test_null_shipment_id.csv', index=False)
print(f"Created test_null_shipment_id.csv with NULL shipment_ids")
print(df)
