# Metodología de indicadores

Todas las fórmulas están implementadas en `src/analytics/metrics.py` (funciones puras, cubiertas por
`tests/test_metrics.py`). Los importes se manejan como **enteros en COP**; los ratios se calculan al final.

## Principios

1. **Sin divisiones inválidas.** Si un denominador es cero, nulo o no hay datos, el indicador vale `None`
   y la interfaz muestra **N/D** con una explicación. Nunca se muestra 0, infinito ni NaN como si fuera un dato.
2. **Sin atribuciones inventadas.** Los gastos operativos no se distribuyen por región, categoría ni producto.
   Con esos filtros activos, la utilidad y el margen operacional se muestran como N/D.
3. **Cifras de gestión, no contables.** Se calculan desde transacciones operativas; no incluyen depreciaciones,
   provisiones, impuestos, gastos financieros ni ajustes de cierre.
4. **Comparaciones homogéneas.** "Periodo anterior" = los N meses inmediatamente anteriores, con N igual a la
   duración del periodo seleccionado. Si ese periodo no está completo en el histórico, no se compara.

## Fórmulas

| Indicador | Fórmula | Implementación | Limitaciones |
|---|---|---|---|
| Ventas brutas (ingresos totales) | Σ cantidad × precio unitario | `enrich_sales_lines` | Antes de descuentos y devoluciones. |
| Devoluciones | unidades devueltas × (ventas brutas − descuento) / cantidad | `enrich_sales_lines` | Se valoran al precio neto efectivamente facturado; redondeo entero half-up. |
| **Ventas netas** | ventas brutas − descuentos − devoluciones | `net_sales` | — |
| Costo de ventas | (cantidad − devueltas) × costo unitario a la fecha de venta | `enrich_sales_lines` | Costo estándar vigente (tabla `costos`), no costo promedio ponderado contable. Las unidades devueltas vuelven al inventario. |
| **Utilidad bruta** | ventas netas − costo de ventas | `gross_profit` | — |
| **Margen bruto** | utilidad bruta / ventas netas × 100 | `gross_margin_pct` | N/D si ventas netas = 0. |
| Gastos operativos | Σ gastos del periodo | `apply_expenses` | Sólo gastos registrados; N/D con filtros de dimensión. |
| **Utilidad operacional** | utilidad bruta − gastos operativos | `operating_profit` | Utilidad de gestión (tipo EBIT simplificado sin depreciación). |
| **Margen operacional** | utilidad operacional / ventas netas × 100 | `operating_margin_pct` | N/D si no hay gastos atribuibles. |
| **Ticket promedio** | ventas netas / número de facturas | `average_ticket` | Una factura = una transacción. |
| **Crecimiento %** | (actual − anterior) / anterior × 100 | `growth_pct` | N/D si el valor anterior es 0, nulo o negativo (sin interpretación económica). |
| Variación en pp | margen actual − margen anterior | `change_pp` | Para comparar porcentajes se usan puntos porcentuales, no %. |
| **Rotación de inventario** | costo de ventas del periodo / inventario promedio | `inventory_turnover` | Inventario promedio = promedio de la foto de apertura (cierre del mes previo) y las fotos de cierre de cada mes del periodo, valorizadas al costo. N/D sin fotos o con inventario promedio 0. |
| Días de inventario | días del periodo / rotación | `days_of_inventory` | Aproximación lineal. |
| Días de cobertura | existencias / demanda diaria promedio de los últimos 90 días | `operational.latest_stock` | N/D si no hubo ventas en 90 días. |
| Nivel de servicio del proveedor | unidades recibidas / unidades pedidas × 100 | `supplier_performance` | Sólo órdenes cerradas (RECIBIDA o PARCIAL). |
| Entregas a tiempo | órdenes recibidas ≤ fecha esperada / órdenes recibidas × 100 | `supplier_performance` | Excluye órdenes pendientes. |
| Participación | valor del elemento / total × 100 | `commercial.by_dimension` | — |
| Concentración HHI | Σ (participación %)², escala 0–10.000 | `commercial.concentration` | < 1.500 baja; 1.500–2.500 moderada; > 2.500 alta (convención usual). |
| Tasa de descuento | descuentos / ventas brutas × 100 | `financial_indicators` | — |
| Tasa de devolución | devoluciones / ventas brutas × 100 | `financial_indicators` | — |

## Segmentación RFM

Implementada en `src/analytics/customers.py`.

- **R (recencia)**: días entre la última compra y la fecha de referencia (día siguiente al cierre del periodo).
- **F (frecuencia)**: número de facturas en el periodo.
- **M (valor)**: ventas netas en el periodo.
- Puntajes 1–5 por **quintiles del ranking** (`rank(method="first")` + `qcut`), robusto ante empates.
- FM = (F + M) / 2. Reglas en orden: Campeones (R≥4, FM≥4) → Leales (R≥3, FM≥3,5) → Nuevos (R≥4, F≤2) →
  Potenciales leales (R≥3) → En riesgo (R≤2, FM≥3,5) → Hibernando (R=2) → Perdidos.
- Requiere al menos 10 clientes; si no, se informa "datos insuficientes" en lugar de segmentar.
- **Limitación**: los quintiles son relativos a la cartera del periodo; un "Campeón" de un periodo débil no
  equivale a uno de un periodo fuerte.

## Estado de actividad de clientes

Usa **todo el historial** hasta la fecha de referencia: *Activo* = compra en los últimos 90 días
(`CBH_ACTIVE_CUSTOMER_DAYS`); *Inactivo* = última compra anterior; *Sin compras* = registrado sin facturas.

## Productos con bajo rendimiento

Producto en el quintil inferior de ventas netas del periodo, **o** con caída mayor al 30 % frente al
periodo anterior de igual duración (si hay base comparable).
