WITH SupplierShipmentDetails AS (
    SELECT
        s.id AS supplier_id,
        s.name AS supplier_name,
        sh.id AS shipment_id,
        sh.ship_date,
        sh.expected_date,
        sh.delivered_date,
        w.name AS warehouse_name,
        o.customer_id,
        CASE
            WHEN sh.delivered_date IS NOT NULL
                 AND sh.expected_date IS NOT NULL
                 AND sh.delivered_date > sh.expected_date
            THEN 1
            ELSE 0
        END AS is_delayed
    FROM suppliers AS s
    INNER JOIN purchase_orders AS po
        ON s.id = po.supplier_id
    INNER JOIN purchase_order_items AS poi
        ON po.id = poi.purchase_order_id
    INNER JOIN products AS p
        ON poi.product_id = p.id
    INNER JOIN order_items AS oi
        ON p.id = oi.product_id
    INNER JOIN orders AS o
        ON oi.order_id = o.id
    INNER JOIN shipments AS sh
        ON o.id = sh.order_id
    INNER JOIN warehouses AS w
        ON sh.warehouse_id = w.id
    WHERE sh.ship_date >= strftime('%Y-%m-%d %H:%M:%S', date('now', '-1 year'))
)
SELECT
    ssd.supplier_id,
    ssd.supplier_name,
    COUNT(DISTINCT ssd.shipment_id) AS total_shipments_count,
    SUM(CASE WHEN ssd.is_delayed = 1 THEN 1 ELSE 0 END) AS delayed_shipments_count,
    CASE
        WHEN COUNT(DISTINCT ssd.shipment_id) > 0 THEN
            CAST(SUM(CASE WHEN ssd.is_delayed = 1 THEN 1 ELSE 0 END) AS REAL) * 100.0
            / COUNT(DISTINCT ssd.shipment_id)
        ELSE 0.0
    END AS percentage_compared_to_total_shipments,
    GROUP_CONCAT(DISTINCT CASE WHEN ssd.is_delayed = 1 THEN ssd.warehouse_name END) AS delayed_warehouses_names,
    GROUP_CONCAT(CASE WHEN ssd.is_delayed = 1 THEN ssd.customer_id END) AS delayed_customer_ids_list
FROM SupplierShipmentDetails AS ssd
GROUP BY
    ssd.supplier_id,
    ssd.supplier_name
HAVING delayed_shipments_count > 0
ORDER BY delayed_shipments_count DESC;
