-- 1. List orders with customer name
-- Corrected table and column names (e.g., orders.id, customers.name).
SELECT
  o.id AS order_id,
  c.name AS customer_name,
  o.order_date
FROM orders o
JOIN customers c ON o.customer_id = c.id
LIMIT 10;

-- 2. Get products and their supplier names
-- Corrected: The 'products' table does not have a supplier_id.
-- This query now finds the relationship through purchase orders to see which suppliers have supplied which products.
SELECT DISTINCT
  s.name AS supplier_name,
  p.name AS product_name
FROM suppliers s
JOIN purchase_orders po ON s.id = po.supplier_id
JOIN purchase_order_items poi ON po.id = poi.purchase_order_id
JOIN products p ON poi.product_id = p.id
LIMIT 10;

-- 3. Find employees handling shipments
-- Corrected: The schema does not link a specific user/employee to a shipment.
-- This query lists recent shipments instead.
SELECT
  s.id AS shipment_id,
  s.tracking_number,
  s.status,
  s.carrier
FROM shipments s
LIMIT 10;

-- 4. List inventory transactions with product names
-- Corrected table names to 'stock_movements' and 'products' and relevant column names.
SELECT
  sm.id AS transaction_id,
  p.name AS product_name,
  sm.movement_type,
  sm.quantity
FROM stock_movements sm
JOIN products p ON sm.product_id = p.id
LIMIT 10;

-- 5. Orders with shipment details
-- Corrected table and column names to be lowercase (orders, shipments, id, ship_date).
SELECT
  o.id AS order_id,
  o.order_date,
  s.ship_date,
  s.status AS shipment_status
FROM orders o
JOIN shipments s ON o.id = s.order_id
LIMIT 10;

-- 6. Customer orders in 2025
-- Corrected table and column names to be lowercase. The logic was correct.
SELECT
  c.name AS customer_name,
  COUNT(o.id) AS total_orders
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE STRFTIME('%Y', o.order_date) = '2025'
GROUP BY c.id;

-- 7. List products stored in each warehouse
-- Corrected the linking table from 'WarehouseProducts' to 'inventory'.
SELECT
  w.name AS warehouse_name,
  p.name AS product_name,
  i.quantity
FROM inventory i
JOIN warehouses w ON i.warehouse_id = w.id
JOIN products p ON i.product_id = p.id
LIMIT 10;

-- 8. Orders with total line items
-- Corrected table and column names to be lowercase (orders, order_items, id).
SELECT
  o.id AS order_id,
  COUNT(oi.id) AS items
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
GROUP BY o.id
LIMIT 10;

-- 9. Supplier product counts
-- Corrected: Similar to query #2, this now correctly counts unique products
-- supplied by each supplier via purchase orders.
SELECT
  s.name AS supplier_name,
  COUNT(DISTINCT poi.product_id) AS unique_products_supplied
FROM suppliers s
JOIN purchase_orders po ON s.id = po.supplier_id
JOIN purchase_order_items poi ON po.id = poi.purchase_order_id
GROUP BY s.id;

-- 10. Employees who processed orders
-- Corrected: The schema does not link a user/employee directly to an order.
-- This query provides a useful alternative: a list of users who are not drivers.
SELECT
  u.full_name AS user_name,
  u.role
FROM users u
WHERE u.role IN ('admin', 'manager', 'staff');