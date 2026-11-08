-- Esquema generado automáticamente desde src/database/models.py
-- Montos en COP como enteros (BIGINT).
PRAGMA foreign_keys = ON;

CREATE TABLE categorias (
	id INTEGER NOT NULL, 
	nombre VARCHAR(60) NOT NULL, 
	descripcion VARCHAR(200), 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);

CREATE TABLE proveedores (
	id INTEGER NOT NULL, 
	codigo VARCHAR(20) NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	ciudad VARCHAR(60) NOT NULL, 
	plazo_pago_dias INTEGER NOT NULL, 
	lead_time_dias INTEGER NOT NULL, 
	origen VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_proveedor_plazo CHECK (plazo_pago_dias >= 0), 
	CONSTRAINT ck_proveedor_lead_time CHECK (lead_time_dias >= 0), 
	UNIQUE (codigo)
);

CREATE TABLE regiones (
	id INTEGER NOT NULL, 
	codigo VARCHAR(10) NOT NULL, 
	nombre VARCHAR(60) NOT NULL, 
	ciudad_principal VARCHAR(60) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	UNIQUE (nombre)
);

CREATE TABLE registro_importaciones (
	id INTEGER NOT NULL, 
	fecha DATETIME NOT NULL, 
	archivo VARCHAR(255) NOT NULL, 
	entidad VARCHAR(40) NOT NULL, 
	filas_leidas INTEGER NOT NULL, 
	filas_cargadas INTEGER NOT NULL, 
	filas_rechazadas INTEGER NOT NULL, 
	duplicados INTEGER NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	detalle TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE clientes (
	id INTEGER NOT NULL, 
	codigo VARCHAR(20) NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	region_id INTEGER NOT NULL, 
	ciudad VARCHAR(60) NOT NULL, 
	fecha_registro DATE NOT NULL, 
	origen VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(region_id) REFERENCES regiones (id) ON DELETE RESTRICT
);
CREATE INDEX ix_clientes_region_id ON clientes (region_id);

CREATE TABLE compras (
	id INTEGER NOT NULL, 
	numero_orden VARCHAR(30) NOT NULL, 
	proveedor_id INTEGER NOT NULL, 
	fecha_orden DATE NOT NULL, 
	fecha_esperada DATE NOT NULL, 
	fecha_recepcion DATE, 
	estado VARCHAR(20) NOT NULL, 
	origen VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_compra_fechas CHECK (fecha_esperada >= fecha_orden), 
	CONSTRAINT ck_compra_estado CHECK (estado IN ('PENDIENTE','RECIBIDA','PARCIAL','CANCELADA')), 
	UNIQUE (numero_orden), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id) ON DELETE RESTRICT
);
CREATE INDEX ix_compras_fecha ON compras (fecha_orden);
CREATE INDEX ix_compras_proveedor_id ON compras (proveedor_id);

CREATE TABLE gastos_operativos (
	id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	categoria_gasto VARCHAR(60) NOT NULL, 
	region_id INTEGER, 
	descripcion VARCHAR(200), 
	monto BIGINT NOT NULL, 
	origen VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_gasto_monto CHECK (monto > 0), 
	FOREIGN KEY(region_id) REFERENCES regiones (id) ON DELETE SET NULL
);
CREATE INDEX ix_gastos_fecha ON gastos_operativos (fecha);

CREATE TABLE productos (
	id INTEGER NOT NULL, 
	sku VARCHAR(30) NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	categoria_id INTEGER NOT NULL, 
	proveedor_id INTEGER, 
	unidad VARCHAR(20) NOT NULL, 
	precio_lista BIGINT NOT NULL, 
	costo_unitario BIGINT NOT NULL, 
	stock_minimo INTEGER NOT NULL, 
	activo BOOLEAN NOT NULL, 
	origen VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_producto_precio CHECK (precio_lista >= 0), 
	CONSTRAINT ck_producto_costo CHECK (costo_unitario >= 0), 
	CONSTRAINT ck_producto_stock_min CHECK (stock_minimo >= 0), 
	UNIQUE (sku), 
	FOREIGN KEY(categoria_id) REFERENCES categorias (id) ON DELETE RESTRICT, 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id) ON DELETE SET NULL
);
CREATE INDEX ix_productos_categoria_id ON productos (categoria_id);
CREATE INDEX ix_productos_proveedor_id ON productos (proveedor_id);

CREATE TABLE vendedores (
	id INTEGER NOT NULL, 
	codigo VARCHAR(20) NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	region_id INTEGER NOT NULL, 
	fecha_ingreso DATE NOT NULL, 
	activo BOOLEAN NOT NULL, 
	origen VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(region_id) REFERENCES regiones (id) ON DELETE RESTRICT
);
CREATE INDEX ix_vendedores_region_id ON vendedores (region_id);

CREATE TABLE costos (
	id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	fecha_vigencia DATE NOT NULL, 
	costo_unitario BIGINT NOT NULL, 
	motivo VARCHAR(120), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_costo_producto_fecha UNIQUE (producto_id, fecha_vigencia), 
	CONSTRAINT ck_costo_valor CHECK (costo_unitario >= 0), 
	FOREIGN KEY(producto_id) REFERENCES productos (id) ON DELETE CASCADE
);

CREATE TABLE detalle_compras (
	id INTEGER NOT NULL, 
	compra_id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	cantidad_pedida INTEGER NOT NULL, 
	cantidad_recibida INTEGER NOT NULL, 
	costo_unitario BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_dc_pedida CHECK (cantidad_pedida > 0), 
	CONSTRAINT ck_dc_recibida CHECK (cantidad_recibida >= 0), 
	CONSTRAINT ck_dc_costo CHECK (costo_unitario >= 0), 
	FOREIGN KEY(compra_id) REFERENCES compras (id) ON DELETE CASCADE, 
	FOREIGN KEY(producto_id) REFERENCES productos (id) ON DELETE RESTRICT
);
CREATE INDEX ix_detalle_compras_compra_id ON detalle_compras (compra_id);
CREATE INDEX ix_detalle_compras_producto_id ON detalle_compras (producto_id);

CREATE TABLE inventario (
	id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	fecha_corte DATE NOT NULL, 
	cantidad INTEGER NOT NULL, 
	costo_unitario BIGINT NOT NULL, 
	valor BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_inventario_producto_corte UNIQUE (producto_id, fecha_corte), 
	CONSTRAINT ck_inv_cantidad CHECK (cantidad >= 0), 
	CONSTRAINT ck_inv_valor CHECK (valor >= 0), 
	FOREIGN KEY(producto_id) REFERENCES productos (id) ON DELETE RESTRICT
);
CREATE INDEX ix_inventario_corte ON inventario (fecha_corte);

CREATE TABLE movimientos_inventario (
	id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	cantidad INTEGER NOT NULL, 
	costo_unitario BIGINT NOT NULL, 
	referencia VARCHAR(40), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_mov_cantidad CHECK (cantidad <> 0), 
	CONSTRAINT ck_mov_tipo CHECK (tipo IN ('INVENTARIO_INICIAL','ENTRADA_COMPRA','SALIDA_VENTA','DEVOLUCION_CLIENTE','AJUSTE')), 
	FOREIGN KEY(producto_id) REFERENCES productos (id) ON DELETE RESTRICT
);
CREATE INDEX ix_mov_producto_fecha ON movimientos_inventario (producto_id, fecha);

CREATE TABLE ventas (
	id INTEGER NOT NULL, 
	numero_factura VARCHAR(30) NOT NULL, 
	fecha DATE NOT NULL, 
	cliente_id INTEGER NOT NULL, 
	vendedor_id INTEGER, 
	region_id INTEGER NOT NULL, 
	canal VARCHAR(30) NOT NULL, 
	origen VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (numero_factura), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id) ON DELETE RESTRICT, 
	FOREIGN KEY(vendedor_id) REFERENCES vendedores (id) ON DELETE SET NULL, 
	FOREIGN KEY(region_id) REFERENCES regiones (id) ON DELETE RESTRICT
);
CREATE INDEX ix_ventas_cliente_fecha ON ventas (cliente_id, fecha);
CREATE INDEX ix_ventas_fecha ON ventas (fecha);
CREATE INDEX ix_ventas_region ON ventas (region_id);
CREATE INDEX ix_ventas_vendedor ON ventas (vendedor_id);

CREATE TABLE detalle_ventas (
	id INTEGER NOT NULL, 
	venta_id INTEGER NOT NULL, 
	producto_id INTEGER NOT NULL, 
	cantidad INTEGER NOT NULL, 
	precio_unitario BIGINT NOT NULL, 
	descuento BIGINT NOT NULL, 
	cantidad_devuelta INTEGER NOT NULL, 
	costo_unitario BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_dv_cantidad CHECK (cantidad > 0), 
	CONSTRAINT ck_dv_precio CHECK (precio_unitario >= 0), 
	CONSTRAINT ck_dv_descuento CHECK (descuento >= 0), 
	CONSTRAINT ck_dv_descuento_max CHECK (descuento <= cantidad * precio_unitario), 
	CONSTRAINT ck_dv_devolucion CHECK (cantidad_devuelta >= 0 AND cantidad_devuelta <= cantidad), 
	CONSTRAINT ck_dv_costo CHECK (costo_unitario >= 0), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id) ON DELETE CASCADE, 
	FOREIGN KEY(producto_id) REFERENCES productos (id) ON DELETE RESTRICT
);
CREATE INDEX ix_detalle_ventas_producto_id ON detalle_ventas (producto_id);
CREATE INDEX ix_detalle_ventas_venta_id ON detalle_ventas (venta_id);
