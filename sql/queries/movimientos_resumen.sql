-- Resumen del kardex por producto: última salida por venta y última entrada.
SELECT p.id AS producto_id, p.sku, p.nombre AS producto, cat.nombre AS categoria,
       MAX(CASE WHEN m.tipo = 'SALIDA_VENTA' THEN m.fecha END)   AS ultima_salida,
       MAX(CASE WHEN m.tipo = 'ENTRADA_COMPRA' THEN m.fecha END) AS ultima_entrada,
       COALESCE(SUM(m.cantidad), 0) AS saldo_kardex
FROM productos p
JOIN categorias cat ON cat.id = p.categoria_id
LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
GROUP BY p.id, p.sku, p.nombre, cat.nombre;
