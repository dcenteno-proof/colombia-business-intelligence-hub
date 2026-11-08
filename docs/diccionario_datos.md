# Diccionario de datos

> Generado automáticamente con `python scripts/generate_schema_docs.py` a partir de `src/database/models.py`. Todos los importes están en **pesos colombianos (COP) como enteros**.

## `categorias`

Categorías de producto.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `nombre` | VARCHAR(60) | No | Único | Nombre descriptivo. |
| `descripcion` | VARCHAR(200) | Sí |  | Descripción libre. |

## `proveedores`

Proveedores de mercancía, con condiciones de pago y tiempo de entrega.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `codigo` | VARCHAR(20) | No | Único | Código de negocio único. |
| `nombre` | VARCHAR(120) | No |  | Nombre descriptivo. |
| `ciudad` | VARCHAR(60) | No |  | Ciudad. |
| `plazo_pago_dias` | INTEGER | No |  | Plazo de pago acordado (días). |
| `lead_time_dias` | INTEGER | No |  | Tiempo de entrega pactado (días). |
| `origen` | VARCHAR(80) | No |  | Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'. |

Restricciones: `plazo_pago_dias >= 0`; `lead_time_dias >= 0`

## `regiones`

Regiones comerciales de Colombia donde opera la distribuidora.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `codigo` | VARCHAR(10) | No | Único | Código de negocio único. |
| `nombre` | VARCHAR(60) | No | Único | Nombre descriptivo. |
| `ciudad_principal` | VARCHAR(60) | No |  | Ciudad principal de la región. |

## `registro_importaciones`

Bitácora del proceso ETL (un registro por archivo importado).

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `fecha` | DATETIME | No |  | Fecha de la transacción. |
| `archivo` | VARCHAR(255) | No |  | Nombre del archivo importado. |
| `entidad` | VARCHAR(40) | No |  | Tipo de información importada. |
| `filas_leidas` | INTEGER | No |  | Filas leídas del archivo. |
| `filas_cargadas` | INTEGER | No |  | Filas insertadas en la base. |
| `filas_rechazadas` | INTEGER | No |  | Filas rechazadas por validación. |
| `duplicados` | INTEGER | No |  | Registros duplicados (archivo + base). |
| `estado` | VARCHAR(20) | No |  | Estado del registro. |
| `detalle` | TEXT | Sí |  | Resumen JSON del proceso (pasos, nulos, muestra de errores). |

## `clientes`

Maestro de clientes (tiendas, minimercados, HORECA, institucionales).

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `codigo` | VARCHAR(20) | No | Único | Código de negocio único. |
| `nombre` | VARCHAR(150) | No |  | Nombre descriptivo. |
| `tipo` | VARCHAR(30) | No |  | Tipo de cliente. |
| `region_id` | INTEGER | No | FK → regiones.id | Región asociada (FK regiones.id). |
| `ciudad` | VARCHAR(60) | No |  | Ciudad. |
| `fecha_registro` | DATE | No |  | Fecha de vinculación del cliente. |
| `origen` | VARCHAR(80) | No |  | Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'. |

Índices: `ix_clientes_region_id` (region_id)

## `compras`

Órdenes de compra a proveedores.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `numero_orden` | VARCHAR(30) | No | Único | Número de orden de compra único. |
| `proveedor_id` | INTEGER | No | FK → proveedores.id | Proveedor (FK proveedores.id). |
| `fecha_orden` | DATE | No |  | Fecha de emisión de la orden. |
| `fecha_esperada` | DATE | No |  | Fecha comprometida de entrega. |
| `fecha_recepcion` | DATE | Sí |  | Fecha real de recepción (nula si está pendiente). |
| `estado` | VARCHAR(20) | No |  | Estado del registro. |
| `origen` | VARCHAR(80) | No |  | Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'. |

Restricciones: `fecha_esperada >= fecha_orden`; `estado IN ('PENDIENTE','RECIBIDA','PARCIAL','CANCELADA')`

Índices: `ix_compras_fecha` (fecha_orden), `ix_compras_proveedor_id` (proveedor_id)

## `gastos_operativos`

Gastos operativos por categoría, región (opcional) y fecha.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `fecha` | DATE | No |  | Fecha de la transacción. |
| `categoria_gasto` | VARCHAR(60) | No |  | Categoría del gasto operativo. |
| `region_id` | INTEGER | Sí | FK → regiones.id | Región asociada (FK regiones.id). |
| `descripcion` | VARCHAR(200) | Sí |  | Descripción libre. |
| `monto` | BIGINT | No |  | Importe del gasto, COP entero (> 0). |
| `origen` | VARCHAR(80) | No |  | Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'. |

Restricciones: `monto > 0`

Índices: `ix_gastos_fecha` (fecha)

## `productos`

Maestro de productos (SKU) con precio de lista y costo vigentes.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `sku` | VARCHAR(30) | No | Único | Código único del producto. |
| `nombre` | VARCHAR(150) | No |  | Nombre descriptivo. |
| `categoria_id` | INTEGER | No | FK → categorias.id | Categoría (FK categorias.id). |
| `proveedor_id` | INTEGER | Sí | FK → proveedores.id | Proveedor (FK proveedores.id). |
| `unidad` | VARCHAR(20) | No |  | Unidad de venta (UND, PAQ). |
| `precio_lista` | BIGINT | No |  | Precio de lista vigente, COP entero. |
| `costo_unitario` | BIGINT | No |  | Costo unitario en COP entero (en detalle: costo vigente a la fecha de la transacción). |
| `stock_minimo` | INTEGER | No |  | Existencia mínima objetivo (unidades). |
| `activo` | BOOLEAN | No |  | Indicador de registro activo. |
| `origen` | VARCHAR(80) | No |  | Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'. |

Restricciones: `stock_minimo >= 0`; `costo_unitario >= 0`; `precio_lista >= 0`

Índices: `ix_productos_categoria_id` (categoria_id), `ix_productos_proveedor_id` (proveedor_id)

## `vendedores`

Fuerza de ventas, asignada a una región.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `codigo` | VARCHAR(20) | No | Único | Código de negocio único. |
| `nombre` | VARCHAR(100) | No |  | Nombre descriptivo. |
| `region_id` | INTEGER | No | FK → regiones.id | Región asociada (FK regiones.id). |
| `fecha_ingreso` | DATE | No |  | Fecha de ingreso del vendedor. |
| `activo` | BOOLEAN | No |  | Indicador de registro activo. |
| `origen` | VARCHAR(80) | No |  | Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'. |

Índices: `ix_vendedores_region_id` (region_id)

## `costos`

Historial del costo unitario por producto (vigencia desde una fecha).

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `producto_id` | INTEGER | No | FK → productos.id Único | Producto (FK productos.id). |
| `fecha_vigencia` | DATE | No | Único | Fecha desde la cual aplica el costo. |
| `costo_unitario` | BIGINT | No |  | Costo unitario en COP entero (en detalle: costo vigente a la fecha de la transacción). |
| `motivo` | VARCHAR(120) | Sí |  | Motivo del cambio de costo. |

Restricciones: `costo_unitario >= 0`

## `detalle_compras`

Líneas de orden de compra: unidades pedidas y recibidas.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `compra_id` | INTEGER | No | FK → compras.id | Orden de compra (FK compras.id). |
| `producto_id` | INTEGER | No | FK → productos.id | Producto (FK productos.id). |
| `cantidad_pedida` | INTEGER | No |  | Unidades pedidas. |
| `cantidad_recibida` | INTEGER | No |  | Unidades efectivamente recibidas. |
| `costo_unitario` | BIGINT | No |  | Costo unitario en COP entero (en detalle: costo vigente a la fecha de la transacción). |

Restricciones: `cantidad_recibida >= 0`; `costo_unitario >= 0`; `cantidad_pedida > 0`

Índices: `ix_detalle_compras_compra_id` (compra_id), `ix_detalle_compras_producto_id` (producto_id)

## `inventario`

Foto del inventario al cierre de cada mes, por producto.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `producto_id` | INTEGER | No | FK → productos.id Único | Producto (FK productos.id). |
| `fecha_corte` | DATE | No | Único | Fecha de corte (cierre de mes) de la foto de inventario. |
| `cantidad` | INTEGER | No |  | Unidades (en kardex con signo: + entrada, - salida). |
| `costo_unitario` | BIGINT | No |  | Costo unitario en COP entero (en detalle: costo vigente a la fecha de la transacción). |
| `valor` | BIGINT | No |  | Valor del inventario al costo = cantidad × costo_unitario (COP). |

Restricciones: `cantidad >= 0`; `valor >= 0`

Índices: `ix_inventario_corte` (fecha_corte)

## `movimientos_inventario`

Kardex: entradas (+) y salidas (-) de unidades por producto.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `producto_id` | INTEGER | No | FK → productos.id | Producto (FK productos.id). |
| `fecha` | DATE | No |  | Fecha de la transacción. |
| `tipo` | VARCHAR(30) | No |  | Tipo de cliente. |
| `cantidad` | INTEGER | No |  | Unidades (en kardex con signo: + entrada, - salida). |
| `costo_unitario` | BIGINT | No |  | Costo unitario en COP entero (en detalle: costo vigente a la fecha de la transacción). |
| `referencia` | VARCHAR(40) | Sí |  | Documento origen del movimiento (factura u orden). |

Restricciones: `cantidad <> 0`; `tipo IN ('INVENTARIO_INICIAL','ENTRADA_COMPRA','SALIDA_VENTA','DEVOLUCION_CLIENTE','AJUSTE')`

Índices: `ix_mov_producto_fecha` (producto_id, fecha)

## `ventas`

Encabezado de factura de venta.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `numero_factura` | VARCHAR(30) | No | Único | Número de factura único. |
| `fecha` | DATE | No |  | Fecha de la transacción. |
| `cliente_id` | INTEGER | No | FK → clientes.id | Cliente (FK clientes.id). |
| `vendedor_id` | INTEGER | Sí | FK → vendedores.id | Vendedor (FK vendedores.id), opcional. |
| `region_id` | INTEGER | No | FK → regiones.id | Región asociada (FK regiones.id). |
| `canal` | VARCHAR(30) | No |  | Canal de venta. |
| `origen` | VARCHAR(80) | No |  | Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'. |

Índices: `ix_ventas_cliente_fecha` (cliente_id, fecha), `ix_ventas_fecha` (fecha), `ix_ventas_region` (region_id), `ix_ventas_vendedor` (vendedor_id)

## `detalle_ventas`

Líneas de factura: cantidades, precio, descuento, devoluciones y costo a la fecha.

| Columna | Tipo | Nulo | Llave | Descripción |
|---|---|---|---|---|
| `id` | INTEGER | No | PK | Identificador interno (llave primaria). |
| `venta_id` | INTEGER | No | FK → ventas.id | Factura (FK ventas.id). |
| `producto_id` | INTEGER | No | FK → productos.id | Producto (FK productos.id). |
| `cantidad` | INTEGER | No |  | Unidades (en kardex con signo: + entrada, - salida). |
| `precio_unitario` | BIGINT | No |  | Precio unitario facturado, COP entero. |
| `descuento` | BIGINT | No |  | Descuento total de la línea, COP entero (0 ≤ descuento ≤ cantidad × precio). |
| `cantidad_devuelta` | INTEGER | No |  | Unidades devueltas por el cliente (0 ≤ devueltas ≤ cantidad). |
| `costo_unitario` | BIGINT | No |  | Costo unitario en COP entero (en detalle: costo vigente a la fecha de la transacción). |

Restricciones: `descuento >= 0`; `descuento <= cantidad * precio_unitario`; `cantidad_devuelta >= 0 AND cantidad_devuelta <= cantidad`; `costo_unitario >= 0`; `cantidad > 0`; `precio_unitario >= 0`

Índices: `ix_detalle_ventas_producto_id` (producto_id), `ix_detalle_ventas_venta_id` (venta_id)
