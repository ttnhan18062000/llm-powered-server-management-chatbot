-- 1. Top 5 customers by total order value
SELECT T2.name, SUM(T3.quantity * T3.unit_price) AS total_value FROM orders AS T1 INNER JOIN customers AS T2 ON T1.customer_id = T2.id INNER JOIN order_items AS T3 ON T1.id = T3.order_id GROUP BY T2.id ORDER BY total_value DESC LIMIT 5;

-- 2. Products that are below reorder level and not restocked recently
SELECT T1.name, T2.quantity AS stock_quantity, T1.reorder_level, MAX(T3.timestamp) AS last_inbound_date FROM products AS T1 INNER JOIN inventory AS T2 ON T1.id = T2.product_id LEFT JOIN stock_movements AS T3 ON T1.id = T3.product_id WHERE T2.quantity < T1.reorder_level AND T3.movement_type = 'inbound' GROUP BY T1.id HAVING last_inbound_date < strftime('%Y-%m-%d %H:%M:%S', date('now', '-30 days'));

-- 3. Average order value per customer
SELECT T2.name, AVG(T1.order_value) AS avg_order FROM (SELECT T1.id, T1.customer_id, SUM(T2.quantity * T2.unit_price) AS order_value FROM orders AS T1 INNER JOIN order_items AS T2 ON T1.id = T2.order_id GROUP BY T1.id) AS T1 INNER JOIN customers AS T2 ON T1.customer_id = T2.id GROUP BY T2.id;

-- 4. Employees with most shipments handled
SELECT T1.carrier, COUNT(T1.id) AS shipments FROM shipments AS T1 GROUP BY T1.carrier ORDER BY shipments DESC LIMIT 5;

-- 5. Products with no orders in the last 6 months
SELECT T1.name FROM products AS T1 WHERE NOT EXISTS (SELECT 1 FROM order_items AS T2 INNER JOIN orders AS T3 ON T2.order_id = T3.id WHERE T2.product_id = T1.id AND T3.order_date >= strftime('%Y-%m-%d %H:%M:%S', date('now', '-6 months')));

-- 6. Warehouse stock value by warehouse
SELECT T1.name, SUM(T2.quantity * T3.unit_price) AS warehouse_value FROM warehouses AS T1 INNER JOIN inventory AS T2 ON T1.id = T2.warehouse_id INNER JOIN products AS T3 ON T2.product_id = T3.id GROUP BY T1.id ORDER BY warehouse_value DESC;

-- 7. Orders that were delayed more than 7 days from order to shipment
SELECT T1.id, T2.name, T1.order_date, T1.shipped_date FROM orders AS T1 INNER JOIN customers AS T2 ON T1.customer_id = T2.id WHERE JULIANDAY(T1.shipped_date) - JULIANDAY(T1.order_date) > 7;

-- 8. Suppliers with top 3 most expensive products
SELECT name, product_name, unit_price FROM (SELECT T1.name, T2.name AS product_name, T2.unit_price, DENSE_RANK() OVER (PARTITION BY T1.id ORDER BY T2.unit_price DESC) AS rank FROM suppliers AS T1 INNER JOIN purchase_order_items AS T3 ON T1.id = T3.purchase_order_id INNER JOIN products AS T2 ON T3.product_id = T2.id) AS T1 WHERE rank <= 3;

-- 9. Monthly sales revenue trend
SELECT strftime('%Y-%m', T1.order_date) AS month, SUM(T2.quantity * T2.unit_price) AS revenue FROM orders AS T1 INNER JOIN order_items AS T2 ON T1.id = T2.order_id GROUP BY month ORDER BY month;

-- 10. Customers who ordered from multiple warehouses
SELECT T1.name, COUNT(DISTINCT T3.warehouse_id) AS warehouse_count FROM customers AS T1 INNER JOIN orders AS T2 ON T1.id = T2.customer_id INNER JOIN shipments AS T3 ON T2.id = T3.order_id GROUP BY T1.id HAVING warehouse_count > 1;