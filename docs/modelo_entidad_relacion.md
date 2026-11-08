# Modelo entidad-relación

Modelo relacional en SQLite definido con SQLAlchemy (`src/database/models.py`). DDL completo:
`sql/schema.sql`. Detalle de columnas: `docs/diccionario_datos.md`.

```mermaid
erDiagram
    REGIONES ||--o{ VENDEDORES : asigna
    REGIONES ||--o{ CLIENTES : ubica
    REGIONES ||--o{ VENTAS : registra
    REGIONES |o--o{ GASTOS_OPERATIVOS : "imputa (opcional)"
    CATEGORIAS ||--o{ PRODUCTOS : agrupa
    PROVEEDORES |o--o{ PRODUCTOS : abastece
    PROVEEDORES ||--o{ COMPRAS : recibe
    CLIENTES ||--o{ VENTAS : realiza
    VENDEDORES |o--o{ VENTAS : gestiona
    VENTAS ||--|{ DETALLE_VENTAS : contiene
    PRODUCTOS ||--o{ DETALLE_VENTAS : vendido_en
    COMPRAS ||--|{ DETALLE_COMPRAS : contiene
    PRODUCTOS ||--o{ DETALLE_COMPRAS : comprado_en
    PRODUCTOS ||--o{ INVENTARIO : "foto mensual"
    PRODUCTOS ||--o{ MOVIMIENTOS_INVENTARIO : kardex
    PRODUCTOS ||--o{ COSTOS : "historial de costo"

    VENTAS {
        int id PK
        string numero_factura UK
        date fecha
        int cliente_id FK
        int vendedor_id FK
        int region_id FK
    }
    DETALLE_VENTAS {
        int id PK
        int venta_id FK
        int producto_id FK
        int cantidad
        bigint precio_unitario
        bigint descuento
        int cantidad_devuelta
        bigint costo_unitario
    }
    PRODUCTOS {
        int id PK
        string sku UK
        int categoria_id FK
        int proveedor_id FK
        bigint precio_lista
        bigint costo_unitario
        int stock_minimo
    }
    INVENTARIO {
        int id PK
        int producto_id FK
        date fecha_corte
        int cantidad
        bigint valor
    }
```

## Decisiones de diseño

| Decisión | Motivo |
|---|---|
| Importes en **BIGINT (COP enteros)** | El peso colombiano no usa centavos en la operación; enteros eliminan errores de redondeo de punto flotante. Los ratios se calculan en la capa analítica. |
| `costo_unitario` copiado en `detalle_ventas` | Foto del costo vigente en la fecha de venta: el margen histórico no cambia si el costo del producto se actualiza después. |
| Tabla `costos` con vigencias | Permite analizar la evolución de costos y detectar incrementos (regla de alertas). |
| `inventario` como foto de fin de mes + `movimientos_inventario` (kardex) | Las fotos permiten calcular inventario promedio y rotación sin reprocesar el kardex; el kardex permite auditar (control de calidad: saldo kardex = última foto). |
| `cantidad` con signo en el kardex | Suma directa del saldo; restricción `cantidad <> 0`. |
| Encabezado/detalle en ventas y compras | Modelo transaccional estándar; el ticket se calcula por factura. |
| Columna `origen` | Trazabilidad: `DEMO` o `IMPORTACION:<archivo>`. |
| `region_id` opcional en gastos | Hay gastos corporativos que no pertenecen a una región. |
| Restricciones CHECK | Cantidades positivas, descuentos ≤ valor bruto, devoluciones ≤ cantidad, montos ≥ 0, estados válidos. |
| `PRAGMA foreign_keys=ON` en cada conexión | SQLite no aplica llaves foráneas por defecto. |
| Índices | Fechas de ventas/compras/gastos, cliente+fecha, región, vendedor, producto+fecha en kardex, fecha de corte. |
