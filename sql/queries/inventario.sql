-- Fotos mensuales de inventario con atributos del producto.
SELECT i.fecha_corte, p.id AS producto_id, p.sku, p.nombre AS producto, cat.nombre AS categoria,
       p.stock_minimo, p.activo, i.cantidad, i.costo_unitario, i.valor
FROM inventario i
JOIN productos p    ON p.id = i.producto_id
JOIN categorias cat ON cat.id = p.categoria_id;
