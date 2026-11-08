SELECT p.id AS producto_id, p.sku, p.nombre AS producto, cat.nombre AS categoria,
       pr.nombre AS proveedor, p.unidad, p.precio_lista, p.costo_unitario, p.stock_minimo, p.activo, p.origen
FROM productos p
JOIN categorias cat ON cat.id = p.categoria_id
LEFT JOIN proveedores pr ON pr.id = p.proveedor_id;
