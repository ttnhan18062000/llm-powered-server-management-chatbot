import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# ================
# 1. Load Schema
# ================
from textwrap import dedent

schema_sql = """ 
-- paste the schema_sql from earlier
"""

db_file = Path("logistics.db")
if db_file.exists():
    db_file.unlink()

conn = sqlite3.connect(str(db_file))
cursor = conn.cursor()
cursor.executescript(schema_sql)

random.seed(42)  # reproducibility


# Utility
def rand_datetime(start_days_ago=30, end_days_ago=0):
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() - timedelta(days=end_days_ago)
    return (start + (end - start) * random.random()).isoformat()


# ================
# 2. Generate Data
# ================

# Warehouses
warehouses = []
for i in range(1, 6):  # 5 warehouses
    warehouses.append(
        (
            f"Warehouse {i}",
            f"WH{i:03d}",
            f"{100+i} Industrial Rd, City {chr(65+i)}",
            round(30 + random.random() * 10, 4),
            round(-90 + random.random() * 10, 4),
            random.randint(5000, 20000),
        )
    )
cursor.executemany(
    "INSERT INTO warehouses (name, code, location, latitude, longitude, capacity) VALUES (?,?,?,?,?,?)",
    warehouses,
)

# Suppliers
suppliers = []
for i in range(1, 11):  # 10 suppliers
    suppliers.append(
        (
            f"Supplier {i}",
            f"Contact {i}",
            f"555-010{i:02d}",
            f"supplier{i}@mail.com",
            f"{i} Supply St, City {chr(65+i)}",
            round(random.uniform(3.0, 5.0), 2),
        )
    )
cursor.executemany(
    "INSERT INTO suppliers (name, contact_name, phone, email, address, rating) VALUES (?,?,?,?,?,?)",
    suppliers,
)

# Customers
customers = []
for i in range(1, 51):  # 50 customers
    customers.append(
        (
            f"Customer {i}",
            random.choice(["individual", "business"]),
            f"Person {i}",
            f"555-020{i:02d}",
            f"cust{i}@mail.com",
            f"{i} Main St, City {chr(65+(i%26))}",
            round(35 + random.random() * 5, 4),
            round(-80 + random.random() * 5, 4),
        )
    )
cursor.executemany(
    "INSERT INTO customers (name, type, contact_name, phone, email, address, latitude, longitude) VALUES (?,?,?,?,?,?,?,?)",
    customers,
)

# Products
products = []
for i in range(1, 201):  # 200 products
    products.append(
        (
            f"SKU{i:05d}",
            f"Product {i}",
            f"Description for product {i}",
            random.choice(["Widgets", "Gadgets", "Parts", "Tools"]),
            round(random.uniform(0.1, 5.0), 2),
            round(random.uniform(0.001, 0.05), 4),
            round(random.uniform(1, 500), 2),
            random.randint(5, 20),
        )
    )
cursor.executemany(
    "INSERT INTO products (sku, name, description, category, weight, volume, unit_price, reorder_level) VALUES (?,?,?,?,?,?,?,?)",
    products,
)

# Inventory (per warehouse-product)
inventory = []
for wh_id in range(1, 6):
    for prod_id in random.sample(
        range(1, 201), 50
    ):  # each warehouse stocks 50 products
        qty = random.randint(50, 500)
        res = random.randint(0, int(qty / 5))
        inventory.append((wh_id, prod_id, qty, res))
cursor.executemany(
    "INSERT INTO inventory (warehouse_id, product_id, quantity, reserved_qty) VALUES (?,?,?,?)",
    inventory,
)

# Orders
orders = []
for i in range(1, 101):  # 100 orders
    cust_id = random.randint(1, 50)
    status = random.choice(
        ["pending", "allocated", "shipped", "delivered", "cancelled"]
    )
    prio = random.randint(0, 3)
    order_date = rand_datetime(30, 0)
    shipped = order_date if status in ["shipped", "delivered"] else None
    delivered = order_date if status == "delivered" else None
    orders.append((cust_id, status, prio, order_date, shipped, delivered))
cursor.executemany(
    "INSERT INTO orders (customer_id, status, priority, order_date, shipped_date, delivered_date) VALUES (?,?,?,?,?,?)",
    orders,
)

# Order Items
order_items = []
for oid in range(1, 101):
    for _ in range(random.randint(1, 5)):
        pid = random.randint(1, 200)
        qty = random.randint(1, 10)
        unit_price = round(random.uniform(5, 500), 2)
        allocated = random.randint(0, qty)
        order_items.append((oid, pid, qty, unit_price, allocated))
cursor.executemany(
    "INSERT INTO order_items (order_id, product_id, quantity, unit_price, allocated_qty) VALUES (?,?,?,?,?)",
    order_items,
)

# Shipments
shipments = []
for sid in range(1, 51):  # 50 shipments
    oid = random.randint(1, 100)
    wh_id = random.randint(1, 5)
    carrier = random.choice(["UPS", "FedEx", "DHL", "USPS"])
    track = f"TRK{sid:05d}"
    status = random.choice(["preparing", "in_transit", "delivered", "failed"])
    ship_date = rand_datetime(15, 0)
    exp_date = (
        datetime.fromisoformat(ship_date) + timedelta(days=random.randint(1, 7))
    ).isoformat()
    del_date = exp_date if status == "delivered" else None
    shipments.append(
        (oid, wh_id, carrier, track, status, ship_date, exp_date, del_date)
    )
cursor.executemany(
    "INSERT INTO shipments (order_id, warehouse_id, carrier, tracking_number, status, ship_date, expected_date, delivered_date) VALUES (?,?,?,?,?,?,?,?)",
    shipments,
)

# Shipment Items
shipment_items = []
for sid in range(1, 51):
    for _ in range(random.randint(1, 3)):
        pid = random.randint(1, 200)
        qty = random.randint(1, 5)
        shipment_items.append((sid, pid, qty))
cursor.executemany(
    "INSERT INTO shipment_items (shipment_id, product_id, quantity) VALUES (?,?,?)",
    shipment_items,
)

# Purchase Orders
purchase_orders = []
for pid in range(1, 51):  # 50 POs
    supp_id = random.randint(1, 10)
    wh_id = random.randint(1, 5)
    status = random.choice(
        ["requested", "approved", "shipped", "received", "cancelled"]
    )
    order_date = rand_datetime(60, 30)
    recv_date = None if status != "received" else rand_datetime(29, 0)
    purchase_orders.append((supp_id, wh_id, status, order_date, recv_date))
cursor.executemany(
    "INSERT INTO purchase_orders (supplier_id, warehouse_id, status, order_date, received_date) VALUES (?,?,?,?,?)",
    purchase_orders,
)

# Purchase Order Items
purchase_order_items = []
for poid in range(1, 51):
    for _ in range(random.randint(1, 4)):
        pid = random.randint(1, 200)
        qty = random.randint(10, 100)
        unit_price = round(random.uniform(1, 400), 2)
        purchase_order_items.append((poid, pid, qty, unit_price))
cursor.executemany(
    "INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
    purchase_order_items,
)

# Stock Movements
movements = []
for _ in range(200):
    wh_id = random.randint(1, 5)
    pid = random.randint(1, 200)
    mtype = random.choice(["inbound", "outbound", "transfer", "adjustment"])
    qty = random.randint(1, 50) * (1 if mtype in ["inbound", "adjustment"] else -1)
    ref_id = random.choice([None, random.randint(1, 100)])
    ref_type = random.choice(["order", "purchase", "shipment", "manual"])
    timestamp = rand_datetime(30, 0)
    notes = f"{mtype} movement"
    movements.append((wh_id, pid, mtype, qty, ref_id, ref_type, timestamp, notes))
cursor.executemany(
    "INSERT INTO stock_movements (warehouse_id, product_id, movement_type, quantity, reference_id, reference_type, timestamp, notes) VALUES (?,?,?,?,?,?,?,?)",
    movements,
)

# Inventory Audits
audits = []
for _ in range(50):
    wh_id = random.randint(1, 5)
    pid = random.randint(1, 200)
    sys_qty = random.randint(50, 500)
    phy_qty = sys_qty + random.randint(-5, 5)
    discrepancy = phy_qty - sys_qty
    audit_date = rand_datetime(10, 0)
    auditor = f"Auditor {random.randint(1,10)}"
    audits.append((wh_id, pid, sys_qty, phy_qty, discrepancy, audit_date, auditor))
cursor.executemany(
    "INSERT INTO inventory_audits (warehouse_id, product_id, system_qty, physical_qty, discrepancy, audit_date, auditor) VALUES (?,?,?,?,?,?,?)",
    audits,
)

# Users
users = []
for i in range(1, 11):
    users.append(
        (
            f"user{i}",
            f"hashed_pw_{i}",
            random.choice(["admin", "manager", "staff", "driver"]),
            f"User {i}",
            f"user{i}@company.com",
        )
    )
cursor.executemany(
    "INSERT INTO users (username, password_hash, role, full_name, email) VALUES (?,?,?,?,?)",
    users,
)

# User Actions
actions = []
for _ in range(200):
    uid = random.randint(1, 10)
    action = random.choice(
        ["CREATE_ORDER", "ALLOCATE_ORDER", "SHIP_ORDER", "INVENTORY_ADJUST", "LOGIN"]
    )
    target_table = random.choice(["orders", "products", "shipments", "inventory"])
    target_id = random.randint(1, 100)
    timestamp = rand_datetime(20, 0)
    details = f"{action} on {target_table} #{target_id}"
    actions.append((uid, action, target_table, target_id, timestamp, details))
cursor.executemany(
    "INSERT INTO user_actions (user_id, action, target_table, target_id, timestamp, details) VALUES (?,?,?,?,?,?)",
    actions,
)

# Commit
conn.commit()
conn.close()
print("✅ logistics_auto.db created with random data")
