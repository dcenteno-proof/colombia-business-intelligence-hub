# Proceso ETL

Implementación: `src/data/etl.py` (`run_etl`). Pruebas: `tests/test_etl.py`. Interfaz: página **Centro de datos**.

## Entidades soportadas

| Entidad | Columnas obligatorias | Opcionales | Llave de duplicado |
|---|---|---|---|
| `clientes` | codigo, nombre, tipo, region, ciudad | fecha_registro | codigo |
| `productos` | sku, nombre, categoria, precio_lista, costo_unitario | unidad, stock_minimo, proveedor_codigo | sku |
| `ventas` (una fila por línea) | numero_factura, fecha, codigo_cliente, sku, cantidad, precio_unitario | descuento, cantidad_devuelta, codigo_vendedor, canal | numero_factura + sku |
| `gastos` | fecha, categoria_gasto, monto | region, descripcion | fecha + categoría + región + descripción + monto |

Los encabezados se normalizan (minúsculas, sin tildes, espacios → `_`) y se reconocen alias comunes
(`Factura`, `Cliente`, `Precio`, `Valor`, `Concepto`…).

## Etapas

1. **Lectura**: CSV (detección automática de separador `,`/`;` y codificación UTF-8/Latin-1) o Excel `.xlsx`.
   Todo se lee como texto para validar sin conversiones implícitas.
2. **Estructura**: verificación de columnas obligatorias. Si falta alguna, el proceso se detiene (FALLIDO).
3. **Limpieza**: espacios redundantes, celdas vacías → nulo, filas totalmente vacías descartadas.
4. **Nulos**: conteo por columna; nulo en columna obligatoria = fila rechazada.
5. **Tipos**: fechas `AAAA-MM-DD` o `DD/MM/AAAA` (no futuras ni anteriores a 2000); cantidades enteras;
   importes en formato colombiano (`$ 1.234.567`, `12.500`) o estándar, redondeados al peso.
6. **Reglas de negocio**: cantidad > 0, precios/costos ≥ 0, 0 ≤ descuento ≤ valor bruto,
   0 ≤ devoluciones ≤ cantidad, monto de gasto > 0.
7. **Normalización**: regiones, categorías, tipos de cliente y categorías de gasto se mapean a sus nombres
   canónicos ignorando mayúsculas/tildes (`"bebidas "` → `Bebidas`, `Pacifico` → `Pacífico`). Una categoría de
   producto nueva se crea con formato capitalizado.
8. **Duplicados**: dentro del archivo (se conserva el primero) y contra la base (se omiten sin error, lo que
   hace la importación **idempotente**).
9. **Referencias**: cliente, producto, vendedor, proveedor y región deben existir. En ventas, todas las líneas de
   una factura deben tener la misma fecha y cliente.
10. **Carga**: transacción única; ante cualquier error de base de datos se revierte todo.
11. **Registro**: fila en `registro_importaciones` con el resumen JSON; CSV de errores en
    `data/processed/etl_errores/`; copia del archivo original en `data/raw/`.

## Estados

`EXITOSO` (todo cargado) · `PARCIAL` (cargado con filas rechazadas) · `SIN_CAMBIOS` (nada nuevo: todo duplicado
o inválido) · `FALLIDO` (estructura inválida, archivo ilegible o error de carga) · `VALIDADO` (modo "validar sin
cargar").

## Archivos de ejemplo

`data/sample/` contiene `ventas_ejemplo.csv`, `clientes_ejemplo.xlsx`, `productos_ejemplo.csv` y
`gastos_ejemplo.xlsx`, con registros válidos y errores intencionales (fecha 31/02, cantidad negativa o decimal,
cliente inexistente, descuento mayor al bruto, duplicados, región inexistente, categorías mal escritas).

## Limitaciones v1

- Las ventas importadas **no** generan movimientos de kardex ni recalculan las fotos de inventario.
- El costo de las líneas importadas es el costo vigente del producto al momento de importar.
- No se soporta actualización (upsert) de registros existentes: los duplicados se omiten.
