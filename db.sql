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