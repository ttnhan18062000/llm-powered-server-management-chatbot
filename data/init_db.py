import sqlite3
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

# ================================
# 0. Configuration & Setup
# ================================

# --- Constants ---
# Adjust these numbers to control the amount of data generated
NUM_WAREHOUSES = 50
NUM_SUPPLIERS = 100
NUM_CUSTOMERS = 500
NUM_PRODUCTS = 2000
NUM_ORDERS = 1000
NUM_PURCHASE_ORDERS = 500
NUM_USERS = 50

# --- Database Setup ---
db_file = Path("logistics_enhanced.db")
if db_file.exists():
    db_file.unlink()

conn = sqlite3.connect(str(db_file))
cursor = conn.cursor()

# --- Schema ---
# It's better to load from file, but for portability, it's embedded here.
schema_sql = """
PRAGMA foreign_keys = ON;

BEGIN;

-- =========================
-- 1) Entities & Core Tables
-- =========================

CREATE TABLE IF NOT EXISTS warehouses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    code            TEXT UNIQUE NOT NULL,
    location        TEXT NOT NULL,
    latitude        REAL,
    longitude       REAL,
    capacity        INTEGER,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    contact_name    TEXT,
    phone           TEXT,
    email           TEXT,
    address         TEXT,
    rating          REAL NOT NULL DEFAULT 0.0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('individual','business')),
    contact_name    TEXT,
    phone           TEXT,
    email           TEXT,
    address         TEXT NOT NULL,
    latitude        REAL,
    longitude       REAL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 2) Products & Inventory
-- =========================

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sku             TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT,
    weight          REAL,
    volume          REAL,
    unit_price      REAL NOT NULL CHECK (unit_price >= 0),
    reorder_level   INTEGER NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity        INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    reserved_qty    INTEGER NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    last_updated    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (warehouse_id, product_id)
);

-- =========================
-- 3) Orders & Fulfillment
-- =========================

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','allocated','shipped','delivered','cancelled')),
    priority        INTEGER NOT NULL DEFAULT 0,
    order_date      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipped_date    DATETIME,
    delivered_date  DATETIME
);

CREATE TABLE IF NOT EXISTS order_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      REAL NOT NULL CHECK (unit_price >= 0),
    allocated_qty   INTEGER NOT NULL DEFAULT 0 CHECK (allocated_qty >= 0)
);

-- =========================
-- 4) Shipments & Tracking
-- =========================

CREATE TABLE IF NOT EXISTS shipments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    carrier         TEXT,
    tracking_number TEXT,
    status          TEXT NOT NULL DEFAULT 'preparing' CHECK (status IN ('preparing','in_transit','delivered','failed')),
    ship_date       DATETIME,
    expected_date   DATETIME,
    delivered_date  DATETIME
);

CREATE TABLE IF NOT EXISTS shipment_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id     INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity        INTEGER NOT NULL CHECK (quantity > 0)
);

-- =========================
-- 5) Purchases & Restocking
-- =========================

CREATE TABLE IF NOT EXISTS purchase_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    status          TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','approved','shipped','received','cancelled')),
    order_date      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    received_date   DATETIME
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id   INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id          INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price          REAL NOT NULL CHECK (unit_price >= 0)
);

-- =========================
-- 6) Movements & Audits
-- =========================

CREATE TABLE IF NOT EXISTS stock_movements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    movement_type   TEXT NOT NULL CHECK (movement_type IN ('inbound','outbound','transfer','adjustment')),
    quantity        INTEGER NOT NULL CHECK (quantity <> 0),
    reference_id    INTEGER,
    reference_type  TEXT CHECK (reference_type IN ('order','purchase','shipment','manual')),
    timestamp       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS inventory_audits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    system_qty      INTEGER NOT NULL,
    physical_qty    INTEGER NOT NULL,
    discrepancy     INTEGER NOT NULL,
    audit_date      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    auditor         TEXT
);

-- =========================
-- 7) Users & Permissions
-- =========================

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin','manager','staff','driver')),
    full_name       TEXT,
    email           TEXT UNIQUE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,
    target_table    TEXT,
    target_id       INTEGER,
    timestamp       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details         TEXT
);

-- =========================
-- 8) Indices
-- =========================

CREATE INDEX IF NOT EXISTS idx_inventory_wh_product ON inventory(warehouse_id, product_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_wh_prod ON stock_movements(warehouse_id, product_id);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);

-- =========================
-- 9) Triggers (timestamps & guards)
-- =========================

-- warehouses.updated_at auto-update
CREATE TRIGGER IF NOT EXISTS trg_warehouses_updated_at
AFTER UPDATE ON warehouses
FOR EACH ROW
BEGIN
    UPDATE warehouses SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- inventory.last_updated auto-update
CREATE TRIGGER IF NOT EXISTS trg_inventory_last_updated
AFTER UPDATE ON inventory
FOR EACH ROW
BEGIN
    UPDATE inventory SET last_updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Prevent reserved > quantity
CREATE TRIGGER IF NOT EXISTS trg_inventory_reserved_guard
BEFORE UPDATE ON inventory
FOR EACH ROW
BEGIN
    SELECT
        CASE
            WHEN NEW.reserved_qty > NEW.quantity THEN
                RAISE(ABORT, 'reserved_qty cannot exceed quantity')
        END;
END;

-- Keep allocated_qty within order item quantity
CREATE TRIGGER IF NOT EXISTS trg_order_items_alloc_guard
BEFORE UPDATE ON order_items
FOR EACH ROW
BEGIN
    SELECT
        CASE
            WHEN NEW.allocated_qty > NEW.quantity THEN
                RAISE(ABORT, 'allocated_qty cannot exceed ordered quantity')
        END;
END;

COMMIT;
"""
cursor.executescript(schema_sql)

# --- Initializers ---
random.seed(42)
fake = Faker()
Faker.seed(42)

# ================================
# 1. Utility Functions
# ================================


def get_db_ids(table_name):
    """Fetch all primary key IDs from a given table."""
    cursor.execute(f"SELECT id FROM {table_name}")
    return [row[0] for row in cursor.fetchall()]


def rand_datetime(start, end):
    """Generate a random datetime between two datetime objects."""
    return (start + (end - start) * random.random()).isoformat(
        sep=" ", timespec="seconds"
    )


def print_progress(entity_name, count):
    """Prints a progress message."""
    print(f"📦 Generating {count} {entity_name}...")


# ================================
# 2. Data Generation Functions
# ================================


def create_warehouses(count):
    print_progress("Warehouses", count)
    warehouses = []
    for i in range(count):
        warehouses.append(
            (
                f"{fake.city()} Distribution Center",
                f"WH{1001+i}",
                fake.street_address(),
                float(fake.latitude()),
                float(fake.longitude()),
                random.randint(10000, 50000),
            )
        )
    cursor.executemany(
        "INSERT INTO warehouses (name, code, location, latitude, longitude, capacity) VALUES (?,?,?,?,?,?)",
        warehouses,
    )


def create_suppliers(count):
    print_progress("Suppliers", count)
    suppliers = []
    for _ in range(count):
        suppliers.append(
            (
                fake.company(),
                fake.name(),
                fake.phone_number(),
                fake.email(),
                fake.address().replace("\n", ", "),
                round(random.uniform(2.5, 5.0), 1),
            )
        )
    cursor.executemany(
        "INSERT INTO suppliers (name, contact_name, phone, email, address, rating) VALUES (?,?,?,?,?,?)",
        suppliers,
    )


def create_customers(count):
    print_progress("Customers", count)
    customers = []
    for _ in range(count):
        cust_type = random.choice(["individual", "business"])
        name = fake.company() if cust_type == "business" else fake.name()
        customers.append(
            (
                name,
                cust_type,
                fake.name(),
                fake.phone_number(),
                fake.email(),
                fake.address().replace("\n", ", "),
                float(fake.latitude()),
                float(fake.longitude()),
            )
        )
    cursor.executemany(
        "INSERT INTO customers (name, type, contact_name, phone, email, address, latitude, longitude) VALUES (?,?,?,?,?,?,?,?)",
        customers,
    )


def create_products(count):
    print_progress("Products", count)
    products = []
    categories = [
        "Electronics",
        "Home Goods",
        "Apparel",
        "Industrial",
        "Groceries",
        "Automotive",
        "Toys",
    ]
    for i in range(count):
        products.append(
            (
                f"SKU{20240000+i}",
                f"{fake.word().capitalize()} {fake.word().capitalize()}",
                fake.sentence(nb_words=10),
                random.choice(categories),
                round(random.uniform(0.1, 50.0), 2),
                round(random.uniform(0.001, 0.2), 4),
                round(random.uniform(5.99, 2999.99), 2),
                random.randint(10, 100),
            )
        )
    cursor.executemany(
        "INSERT INTO products (sku, name, description, category, weight, volume, unit_price, reorder_level) VALUES (?,?,?,?,?,?,?,?)",
        products,
    )


def create_inventory():
    warehouse_ids = get_db_ids("warehouses")
    product_ids = get_db_ids("products")
    print_progress(
        "Inventory (Stock)", f"{len(warehouse_ids) * int(len(product_ids) * 0.4)}"
    )

    inventory = []
    # Each warehouse stocks ~40% of all products
    for wh_id in warehouse_ids:
        stocked_products = random.sample(product_ids, int(len(product_ids) * 0.4))
        for prod_id in stocked_products:
            qty = random.randint(0, 1000)  # Some items can be out of stock
            res = (
                0 if qty == 0 else random.randint(0, int(qty * 0.2))
            )  # Reserve up to 20%
            inventory.append((wh_id, prod_id, qty, res))

    cursor.executemany(
        "INSERT INTO inventory (warehouse_id, product_id, quantity, reserved_qty) VALUES (?,?,?,?)",
        inventory,
    )


def create_orders_and_items(order_count):
    print_progress("Orders & Order Items", order_count)
    customer_ids = get_db_ids("customers")
    product_ids = get_db_ids("products")

    orders = []
    order_items = []

    now = datetime.now()

    for order_id in range(1, order_count + 1):
        customer_id = random.choice(customer_ids)
        status = random.choices(
            ["pending", "allocated", "shipped", "delivered", "cancelled"],
            [0.1, 0.1, 0.3, 0.4, 0.1],
        )[0]

        # Logical date generation
        order_date = datetime.fromisoformat(
            rand_datetime(now - timedelta(days=365), now)
        )
        shipped_date, delivered_date = None, None

        if status in ["shipped", "delivered"]:
            shipped_date = rand_datetime(order_date, order_date + timedelta(days=3))
            if status == "delivered":
                delivered_date = rand_datetime(
                    datetime.fromisoformat(shipped_date),
                    datetime.fromisoformat(shipped_date) + timedelta(days=14),
                )

        orders.append(
            (
                customer_id,
                status,
                random.randint(0, 5),
                order_date.isoformat(sep=" ", timespec="seconds"),
                shipped_date,
                delivered_date,
            )
        )

        # Order Items
        for _ in range(random.randint(1, 8)):
            product_id = random.choice(product_ids)
            qty = random.randint(1, 20)

            # Get product price, but add slight variation for realism
            cursor.execute("SELECT unit_price FROM products WHERE id=?", (product_id,))
            base_price = cursor.fetchone()[0]
            price_at_order = base_price * random.uniform(0.98, 1.02)

            allocated = 0
            if status == "allocated":
                allocated = random.randint(0, qty)
            elif status in ["shipped", "delivered"]:
                allocated = qty

            order_items.append(
                (order_id, product_id, qty, round(price_at_order, 2), allocated)
            )

    cursor.executemany(
        "INSERT INTO orders (customer_id, status, priority, order_date, shipped_date, delivered_date) VALUES (?,?,?,?,?,?)",
        orders,
    )
    cursor.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price, allocated_qty) VALUES (?,?,?,?,?)",
        order_items,
    )


def create_shipments_and_items():
    print_progress("Shipments & Items", "")
    # Find orders that are 'shipped' or 'delivered' to create shipments for them
    cursor.execute(
        "SELECT id, order_date FROM orders WHERE status IN ('shipped', 'delivered')"
    )
    shippable_orders = cursor.fetchall()

    warehouse_ids = get_db_ids("warehouses")
    shipments = []
    shipment_items = []

    shipment_id_counter = 1
    for order_id, order_date_str in shippable_orders:
        warehouse_id = random.choice(warehouse_ids)
        carrier = random.choice(["UPS", "FedEx", "DHL", "USPS", "Local Courier"])

        order_date = datetime.fromisoformat(order_date_str)
        ship_date = datetime.fromisoformat(
            rand_datetime(order_date, order_date + timedelta(days=2))
        )
        expected_date = ship_date + timedelta(days=random.randint(2, 10))

        cursor.execute(
            "SELECT status, delivered_date FROM orders WHERE id = ?", (order_id,)
        )
        order_status, delivered_date_str = cursor.fetchone()

        ship_status = (
            "delivered"
            if order_status == "delivered"
            else random.choices(
                ["in_transit", "delivered", "failed"], [0.7, 0.25, 0.05]
            )[0]
        )

        delivered_date = None
        if ship_status == "delivered":
            delivered_date = delivered_date_str or rand_datetime(
                ship_date, expected_date + timedelta(days=5)
            )

        shipments.append(
            (
                order_id,
                warehouse_id,
                carrier,
                fake.ean(length=13),
                ship_status,
                ship_date.isoformat(sep=" ", timespec="seconds"),
                expected_date.isoformat(sep=" ", timespec="seconds"),
                delivered_date,
            )
        )

        # Shipment items from order items
        cursor.execute(
            "SELECT product_id, quantity FROM order_items WHERE order_id=?", (order_id,)
        )
        items_to_ship = cursor.fetchall()
        for product_id, quantity in items_to_ship:
            shipment_items.append((shipment_id_counter, product_id, quantity))

        shipment_id_counter += 1

    cursor.executemany(
        "INSERT INTO shipments (order_id, warehouse_id, carrier, tracking_number, status, ship_date, expected_date, delivered_date) VALUES (?,?,?,?,?,?,?,?)",
        shipments,
    )
    cursor.executemany(
        "INSERT INTO shipment_items (shipment_id, product_id, quantity) VALUES (?,?,?)",
        shipment_items,
    )


def create_purchase_orders_and_items(po_count):
    print_progress("Purchase Orders & Items", po_count)
    supplier_ids = get_db_ids("suppliers")
    warehouse_ids = get_db_ids("warehouses")
    product_ids = get_db_ids("products")

    purchase_orders = []
    po_items = []
    now = datetime.now()

    for po_id in range(1, po_count + 1):
        status = random.choices(
            ["requested", "approved", "shipped", "received", "cancelled"],
            [0.1, 0.1, 0.2, 0.5, 0.1],
        )[0]
        order_date = datetime.fromisoformat(
            rand_datetime(now - timedelta(days=90), now)
        )
        received_date = None
        if status == "received":
            received_date = rand_datetime(order_date + timedelta(days=7), now)

        purchase_orders.append(
            (
                random.choice(supplier_ids),
                random.choice(warehouse_ids),
                status,
                order_date.isoformat(sep=" ", timespec="seconds"),
                received_date,
            )
        )

        for _ in range(random.randint(2, 10)):
            product_id = random.choice(product_ids)
            cursor.execute("SELECT unit_price FROM products WHERE id=?", (product_id,))
            base_price = cursor.fetchone()[0]
            cost_price = base_price * random.uniform(0.4, 0.7)  # Supplier price
            po_items.append(
                (po_id, product_id, random.randint(50, 500), round(cost_price, 2))
            )

    cursor.executemany(
        "INSERT INTO purchase_orders (supplier_id, warehouse_id, status, order_date, received_date) VALUES (?,?,?,?,?)",
        purchase_orders,
    )
    cursor.executemany(
        "INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
        po_items,
    )


def create_stock_movements():
    print_progress("Logical Stock Movements", "")
    movements = []

    # 1. Outbound for shipped orders
    cursor.execute(
        """
        SELECT s.id, s.warehouse_id, si.product_id, si.quantity, s.ship_date
        FROM shipments s JOIN shipment_items si ON s.id = si.shipment_id
        WHERE s.status IN ('in_transit', 'delivered')
    """
    )
    for ship_id, wh_id, prod_id, qty, ts in cursor.fetchall():
        movements.append(
            (
                wh_id,
                prod_id,
                "outbound",
                -qty,
                ship_id,
                "shipment",
                ts,
                f"Shipment ID: {ship_id}",
            )
        )

    # 2. Inbound for received purchase orders
    cursor.execute(
        """
        SELECT po.id, po.warehouse_id, poi.product_id, poi.quantity, po.received_date
        FROM purchase_orders po JOIN purchase_order_items poi ON po.id = poi.purchase_order_id
        WHERE po.status = 'received' AND po.received_date IS NOT NULL
    """
    )
    for po_id, wh_id, prod_id, qty, ts in cursor.fetchall():
        movements.append(
            (wh_id, prod_id, "inbound", qty, po_id, "purchase", ts, f"PO ID: {po_id}")
        )

    # 3. Random adjustments
    warehouse_ids = get_db_ids("warehouses")
    product_ids = get_db_ids("products")
    for _ in range(200):  # Add 200 random adjustments
        qty = random.randint(-20, 20)
        if qty == 0:
            continue
        movements.append(
            (
                random.choice(warehouse_ids),
                random.choice(product_ids),
                "adjustment",
                qty,
                None,
                "manual",
                rand_datetime(datetime.now() - timedelta(days=30), datetime.now()),
                random.choice(
                    ["Cycle count adjustment", "Damaged goods", "Found inventory"]
                ),
            )
        )

    cursor.executemany(
        "INSERT INTO stock_movements (warehouse_id, product_id, movement_type, quantity, reference_id, reference_type, timestamp, notes) VALUES (?,?,?,?,?,?,?,?)",
        movements,
    )


def create_users(count):
    print_progress("Users", count)
    users = []
    for i in range(count):
        fname = fake.first_name()
        lname = fake.last_name()
        users.append(
            (
                f"{fname.lower()}{i}",
                fake.password(length=12),  # In a real app, this would be a hash
                random.choices(
                    ["admin", "manager", "staff", "driver"], [0.1, 0.2, 0.6, 0.1]
                )[0],
                f"{fname} {lname}",
                f"{fname.lower()}.{lname.lower()}{i}@{fake.free_email_domain()}",
            )
        )
    cursor.executemany(
        "INSERT INTO users (username, password_hash, role, full_name, email) VALUES (?,?,?,?,?)",
        users,
    )


# ================================
# 3. Main Execution
# ================================


def main():
    start_time = time.time()
    print("🚀 Starting enhanced database mock script...")

    conn.execute("BEGIN")
    try:
        create_warehouses(NUM_WAREHOUSES)
        create_suppliers(NUM_SUPPLIERS)
        create_customers(NUM_CUSTOMERS)
        create_products(NUM_PRODUCTS)
        create_inventory()
        create_orders_and_items(NUM_ORDERS)
        create_shipments_and_items()
        create_purchase_orders_and_items(NUM_PURCHASE_ORDERS)
        create_stock_movements()
        create_users(NUM_USERS)

        # ... (audits and user_actions can be added similarly) ...

        conn.commit()

    except sqlite3.Error as e:
        print(f"❌ An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

    end_time = time.time()
    print(
        f"\n✅ logistics_enhanced.db created successfully in {end_time - start_time:.2f} seconds."
    )


if __name__ == "__main__":
    main()
