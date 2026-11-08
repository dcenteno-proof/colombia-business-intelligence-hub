-- Historial de costos unitarios por producto.
SELECT c.fecha_vigencia, p.id AS producto_id, p.sku, p.nombre AS producto, cat.nombre AS categoria,
       c.costo_unitario, c.motivo
FROM costos c
JOIN productos p    ON p.id = c.producto_id
JOIN categorias cat ON cat.id = p.categoria_id;
