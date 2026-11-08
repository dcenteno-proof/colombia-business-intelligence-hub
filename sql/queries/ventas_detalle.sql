-- Hechos de venta a nivel de línea de factura.
-- Parámetros: :fecha_inicio, :fecha_fin (texto ISO YYYY-MM-DD, inclusive).
SELECT
    dv.id                AS linea_id,
    v.id                 AS venta_id,
    v.numero_factura,
    v.fecha,
    v.canal,
    v.origen,
    c.id                 AS cliente_id,
    c.codigo             AS cliente_codigo,
    c.nombre             AS cliente,
    c.tipo               AS tipo_cliente,
    r.nombre             AS region,
    COALESCE(ve.nombre, 'Sin vendedor') AS vendedor,
    p.id                 AS producto_id,
    p.sku,
    p.nombre             AS producto,
    cat.nombre           AS categoria,
    dv.cantidad,
    dv.cantidad_devuelta,
    dv.precio_unitario,
    dv.descuento,
    dv.costo_unitario
FROM detalle_ventas dv
JOIN ventas v        ON v.id = dv.venta_id
JOIN clientes c      ON c.id = v.cliente_id
JOIN regiones r      ON r.id = v.region_id
LEFT JOIN vendedores ve ON ve.id = v.vendedor_id
JOIN productos p     ON p.id = dv.producto_id
JOIN categorias cat  ON cat.id = p.categoria_id
WHERE v.fecha BETWEEN :fecha_inicio AND :fecha_fin;
