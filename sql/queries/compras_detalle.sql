-- Compras a nivel de línea. Parámetros: :fecha_inicio, :fecha_fin (sobre fecha_orden).
SELECT dc.id AS linea_id, co.id AS compra_id, co.numero_orden, co.fecha_orden, co.fecha_esperada,
       co.fecha_recepcion, co.estado, pr.codigo AS proveedor_codigo, pr.nombre AS proveedor,
       p.sku, p.nombre AS producto, cat.nombre AS categoria,
       dc.cantidad_pedida, dc.cantidad_recibida, dc.costo_unitario
FROM detalle_compras dc
JOIN compras co     ON co.id = dc.compra_id
JOIN proveedores pr ON pr.id = co.proveedor_id
JOIN productos p    ON p.id = dc.producto_id
JOIN categorias cat ON cat.id = p.categoria_id
WHERE co.fecha_orden BETWEEN :fecha_inicio AND :fecha_fin;
