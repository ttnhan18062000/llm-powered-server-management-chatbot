WITH DelayedShipments AS (
    SELECT
        s.id AS shipment_id,
        s.order_id,
        s.warehouse_id,
        s.ship_date,
        s.expected_date,
        s.status,
        o.customer_id
    FROM shipments AS s
    JOIN orders AS o ON s.order_id = o.id
    WHERE s.status IN ('in_transit', 'failed')
      AND (
          s.ship_date BETWEEN strftime('%Y-01-01', date('now', '-1 year')) AND date('now')
          OR s.expected_date BETWEEN strftime('%Y-01-01', date('now', '-1 year')) AND date('now')
      )
),
SupplierShipments AS (
    SELECT
        po.supplier_id,
        ds.shipment_id,
        ds.warehouse_id,
        ds.order_id,
        ds.customer_id
    FROM DelayedShipments AS ds
    JOIN orders AS o ON ds.order_id = o.id
    JOIN order_items AS oi ON o.id = oi.order_id
    JOIN products AS p ON oi.product_id = p.id
    JOIN purchase_order_items AS poi ON p.id = poi.product_id
    JOIN purchase_orders AS po ON poi.purchase_order_id = po.id
)
SELECT
    s.supplier_id,
    sup.name AS supplier_name,
    COUNT(s.shipment_id) AS num_delayed_shipments,
    CAST(COUNT(s.shipment_id) AS REAL) * 100 /
        (SELECT COUNT(shipment_id)
         FROM SupplierShipments ss
         WHERE ss.supplier_id = s.supplier_id) AS percentage_delayed,
    GROUP_CONCAT(DISTINCT w.name) AS affected_warehouses,
    (
        SELECT GROUP_CONCAT(name, '; ')
        FROM (
            SELECT DISTINCT c2.name
            FROM customers c2
            JOIN SupplierShipments s2 ON c2.id = s2.customer_id
            WHERE s2.supplier_id = s.supplier_id
        )
    ) AS top_customers
FROM SupplierShipments AS s
JOIN suppliers AS sup ON s.supplier_id = sup.id
JOIN warehouses AS w ON s.warehouse_id = w.id
JOIN customers AS c ON s.customer_id = c.id
GROUP BY s.supplier_id
ORDER BY num_delayed_shipments DESC
LIMIT 10;
