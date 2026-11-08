# Reglas del centro de alertas

Implementación: `src/analytics/alerts.py` (clase `AlertEngine`). Pruebas: `tests/test_alerts_reports.py`.

## Funcionamiento general

- Se evalúa el **último mes completo** hasta el cierre del periodo seleccionado. Un mes se considera completo si
  la última venta registrada cae en sus últimos 3 días; si no, se evalúa el mes anterior.
- Las alertas son **a nivel compañía** (no usan filtros de región/categoría/producto).
- La base de comparación es el **promedio de los 3 meses previos**, más robusta que el mes anterior aislado.
- Cada regla verifica primero si hay datos suficientes. **Si no los hay, no se genera alerta** y la evaluación
  queda registrada como "Sin datos suficientes".
- Cada alerta muestra: motivo, indicador afectado, valor observado, umbral y recomendación.
- Severidad **Alta** cuando la desviación duplica el umbral; **Media** en los demás casos.
- Una regla que falle por un error técnico no detiene las demás (queda en estado "Error").

## Reglas

| Regla | Indicador | Dispara si | Datos mínimos | Umbral (.env) |
|---|---|---|---|---|
| Caída de ventas | Ventas netas del mes vs promedio 3 meses previos | Caída ≥ 15 %, **salvo** que el crecimiento anual (mismo mes del año anterior) sea ≥ 0 (estacionalidad) | 3 meses previos | `CBH_ALERT_SALES_DROP_PCT` |
| Caída de ventas por región | Ídem, por región | Caída ≥ 20 % en regiones con ≥ 3 % de participación | 3 meses previos | `CBH_ALERT_REGION_DROP_PCT` |
| Disminución de margen | Margen bruto total y por categoría (pp vs 3 meses) | Total ≤ −2 pp; categoría (≥ 3 % de ventas) ≤ −3 pp | 3 meses previos | `CBH_ALERT_MARGIN_DROP_PP`, `CBH_ALERT_CAT_MARGIN_DROP_PP` |
| Inventario bajo | Existencias en la última foto ≤ stock mínimo | Producto activo bajo mínimo | Fotos de inventario | `productos.stock_minimo` |
| Concentración de ventas | Participación del cliente principal y del top 10 (últimos 3 meses) | Top 1 > 10 % o top 10 > 50 % | ≥ 20 clientes con compras | `CBH_ALERT_TOP1_SHARE_PCT`, `CBH_ALERT_TOP10_SHARE_PCT`, `CBH_ALERT_MIN_CUSTOMERS` |
| Aumento de costos | Variación del costo unitario en 90 días, agrupada por categoría | Productos con aumento > 8 % | 90 días de historial de costos | `CBH_ALERT_COST_INCREASE_PCT` |
| Gastos operativos elevados | Gastos/ventas del mes y crecimiento vs 3 meses | Gastos/ventas > 24 % o crecimiento > 15 % | 3 meses previos con gastos | `CBH_ALERT_OPEX_RATIO_PCT`, `CBH_ALERT_OPEX_INCREASE_PCT` |

## Escenarios incluidos en los datos DEMO

El generador incorpora, en el último mes, situaciones que las reglas deben detectar: caída de demanda en la
región Caribe, aumento de costo en Lácteos y aceites sin ajuste de precio, campaña de marketing y sobrecostos
logísticos, cinco productos bajo mínimo y dos productos descontinuados sin movimiento.
