-- Gastos operativos. Parámetros: :fecha_inicio, :fecha_fin.
SELECT g.id, g.fecha, g.categoria_gasto, COALESCE(r.nombre, 'Corporativo') AS region,
       g.descripcion, g.monto, g.origen
FROM gastos_operativos g
LEFT JOIN regiones r ON r.id = g.region_id
WHERE g.fecha BETWEEN :fecha_inicio AND :fecha_fin;
