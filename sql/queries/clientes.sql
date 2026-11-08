SELECT c.id AS cliente_id, c.codigo, c.nombre AS cliente, c.tipo AS tipo_cliente, r.nombre AS region,
       c.ciudad, c.fecha_registro, c.origen
FROM clientes c
JOIN regiones r ON r.id = c.region_id;
