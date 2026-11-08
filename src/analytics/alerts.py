"""Centro de alertas: reglas de negocio documentadas y auditables.

Cada regla:
  1. Verifica primero si hay datos suficientes. Si no los hay, NO genera alerta
     y deja constancia en la evaluación ("Sin datos suficientes").
  2. Calcula el indicador con las fórmulas de ``metrics``.
  3. Compara contra un umbral configurable (``AlertThresholds`` / .env).
  4. Si se dispara, produce una alerta con motivo, indicador, valor observado,
     umbral y recomendación.

Las reglas se evalúan sobre el ÚLTIMO MES COMPLETO disponible hasta el cierre
del periodo seleccionado, a nivel de toda la compañía (sin filtros de dimensión).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from src.analytics import operational as op
from src.analytics.commercial import concentration
from src.analytics.metrics import change_pp, growth_pct, pct
from src.config import AlertThresholds

SEVERITY_ORDER = {"Alta": 0, "Media": 1, "Baja": 2}


@dataclass
class Alert:
    regla: str
    severidad: str
    modulo: str
    titulo: str
    motivo: str
    indicador: str
    valor_observado: str
    umbral: str
    recomendacion: str
    periodo: str


@dataclass
class RuleEvaluation:
    regla: str
    estado: str      # "Alerta" | "Sin alerta" | "Sin datos suficientes"
    detalle: str


def _fmt_pct(v: float | None, decimals: int = 1) -> str:
    return "N/D" if v is None else f"{v:,.{decimals}f} %".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pp(v: float | None) -> str:
    return "N/D" if v is None else f"{v:+.1f} pp".replace(".", ",")


def _fmt_cop(v) -> str:
    return "N/D" if v is None else "$ " + f"{int(round(v)):,}".replace(",", ".")


def last_complete_month(lines: pd.DataFrame, end_month: str | None = None) -> str | None:
    """Último mes con información completa (el mes de la última venta cuenta como
    completo sólo si la última venta ocurre en los últimos 3 días del mes)."""
    if lines.empty:
        return None
    data = lines if end_month is None else lines[lines["mes"] <= end_month]
    if data.empty:
        return None
    max_date = pd.Timestamp(data["fecha"].max())
    month = max_date.to_period("M")
    if max_date < month.end_time.normalize() - pd.Timedelta(days=3):
        month = month - 1
    return str(month)


class AlertEngine:
    def __init__(self, lines: pd.DataFrame, expenses: pd.DataFrame, snapshots: pd.DataFrame,
                 cost_history: pd.DataFrame, thresholds: AlertThresholds | None = None,
                 end_month: str | None = None) -> None:
        self.t = thresholds or AlertThresholds()
        self.month = last_complete_month(lines, end_month)
        self.lines = lines[lines["mes"] <= self.month] if self.month else lines.iloc[0:0]
        self.expenses = expenses[expenses["mes"] <= self.month] if self.month and not expenses.empty else expenses
        self.snapshots = snapshots
        self.cost_history = cost_history
        self.alerts: list[Alert] = []
        self.evaluations: list[RuleEvaluation] = []
        months = sorted(self.lines["mes"].unique()) if not self.lines.empty else []
        self.months = months

    # ----------------------------------------------------------- utilidades
    def _prev_months(self, n: int) -> list[str]:
        if self.month not in self.months:
            return []
        i = self.months.index(self.month)
        return self.months[max(0, i - n):i]

    def _enough_history(self, rule: str) -> bool:
        prev = self._prev_months(self.t.min_months_history)
        if self.month is None or len(prev) < self.t.min_months_history:
            self.evaluations.append(RuleEvaluation(
                rule, "Sin datos suficientes",
                f"Se requieren {self.t.min_months_history} meses previos completos; hay {len(prev)}."))
            return False
        return True

    def _add(self, **kw) -> None:
        self.alerts.append(Alert(periodo=self.month or "", **kw))

    # ---------------------------------------------------------------- reglas
    def rule_sales_drop(self) -> None:
        rule = "Caída de ventas"
        if not self._enough_history(rule):
            return
        monthly = self.lines.groupby("mes").ventas_netas.sum()
        prev = self._prev_months(3)
        current, baseline = monthly[self.month], monthly[prev].mean()
        g = growth_pct(current, baseline)
        yoy_month = str(pd.Period(self.month, "M") - 12)
        yoy = growth_pct(current, monthly.get(yoy_month)) if yoy_month in monthly.index else None
        if g is None:
            self.evaluations.append(RuleEvaluation(rule, "Sin datos suficientes", "Base de comparación en cero."))
            return
        if g <= -self.t.sales_drop_pct:
            if yoy is not None and yoy >= 0:
                self.evaluations.append(RuleEvaluation(
                    rule, "Sin alerta", f"Caída {_fmt_pct(g)} vs promedio 3 meses, pero crecimiento anual "
                                        f"{_fmt_pct(yoy)}: comportamiento estacional."))
                return
            self._add(regla=rule, severidad="Alta" if g <= -2 * self.t.sales_drop_pct else "Media", modulo="Comercial",
                      titulo=f"Ventas netas cayeron {_fmt_pct(abs(g))} en {self.month}",
                      motivo=f"Ventas netas de {self.month} frente al promedio de {', '.join(prev)}."
                             + (f" Variación anual: {_fmt_pct(yoy)}." if yoy is not None else ""),
                      indicador="Crecimiento de ventas netas vs promedio 3 meses", valor_observado=_fmt_pct(g),
                      umbral=f"≤ -{_fmt_pct(self.t.sales_drop_pct)}",
                      recomendacion="Revisar por región, vendedor y categoría el origen de la caída; validar "
                                    "quiebres de inventario y pérdida de clientes principales.")
            self.evaluations.append(RuleEvaluation(rule, "Alerta", f"Variación {_fmt_pct(g)}."))
        else:
            self.evaluations.append(RuleEvaluation(rule, "Sin alerta", f"Variación {_fmt_pct(g)} vs promedio 3 meses."))

    def rule_region_drop(self) -> None:
        rule = "Caída de ventas por región"
        if not self._enough_history(rule):
            return
        prev = self._prev_months(3)
        pivot = self.lines.groupby(["region", "mes"]).ventas_netas.sum().unstack(fill_value=0)
        total_base = pivot[prev].sum().sum()
        fired = 0
        for region, row in pivot.iterrows():
            base = row[prev].mean()
            share = pct(row[prev].sum(), total_base) or 0
            if share < 3:  # regiones con muy poca base no son concluyentes
                continue
            g = growth_pct(row.get(self.month, 0), base)
            if g is not None and g <= -self.t.region_sales_drop_pct:
                fired += 1
                self._add(regla=rule, severidad="Alta" if g <= -2 * self.t.region_sales_drop_pct else "Media",
                          modulo="Comercial", titulo=f"Caída de ventas en {region}: {_fmt_pct(g)}",
                          motivo=f"Ventas netas de {region} en {self.month} ({_fmt_cop(row.get(self.month, 0))}) "
                                 f"frente al promedio de los 3 meses previos ({_fmt_cop(base)}).",
                          indicador="Crecimiento de ventas netas regionales vs promedio 3 meses",
                          valor_observado=_fmt_pct(g), umbral=f"≤ -{_fmt_pct(self.t.region_sales_drop_pct)}",
                          recomendacion=f"Revisar cobertura de rutas, cumplimiento de entregas y cartera de clientes "
                                        f"en {region}; contrastar con la actividad de los vendedores de la zona.")
        self.evaluations.append(RuleEvaluation(rule, "Alerta" if fired else "Sin alerta",
                                               f"{fired} regiones bajo el umbral."))

    def rule_margin_drop(self) -> None:
        rule = "Disminución de margen bruto"
        if not self._enough_history(rule):
            return
        prev = self._prev_months(3)

        def margin(df: pd.DataFrame) -> float | None:
            return pct(df["utilidad_bruta"].sum(), df["ventas_netas"].sum())

        cur_df = self.lines[self.lines["mes"] == self.month]
        base_df = self.lines[self.lines["mes"].isin(prev)]
        d = change_pp(margin(cur_df), margin(base_df))
        fired = 0
        if d is not None and d <= -self.t.margin_drop_pp:
            fired += 1
            self._add(regla=rule, severidad="Alta" if d <= -2 * self.t.margin_drop_pp else "Media", modulo="Financiero",
                      titulo=f"Margen bruto bajó {_fmt_pp(d)} en {self.month}",
                      motivo=f"Margen bruto {_fmt_pct(margin(cur_df))} vs {_fmt_pct(margin(base_df))} promedio "
                             f"de {', '.join(prev)}.",
                      indicador="Margen bruto (pp vs promedio 3 meses)", valor_observado=_fmt_pp(d),
                      umbral=f"≤ -{self.t.margin_drop_pp:.1f} pp".replace(".", ","),
                      recomendacion="Revisar costos de proveedor, política de descuentos y mezcla de productos; "
                                    "evaluar ajuste de precios de lista.")
        total = cur_df["ventas_netas"].sum()
        for cat in sorted(self.lines["categoria"].unique()):
            c_cur, c_base = cur_df[cur_df["categoria"] == cat], base_df[base_df["categoria"] == cat]
            if c_cur.empty or c_base.empty or (pct(c_cur["ventas_netas"].sum(), total) or 0) < 3:
                continue
            dc = change_pp(margin(c_cur), margin(c_base))
            if dc is not None and dc <= -self.t.category_margin_drop_pp:
                fired += 1
                self._add(regla=rule, severidad="Alta" if dc <= -2 * self.t.category_margin_drop_pp else "Media",
                          modulo="Financiero", titulo=f"Margen de {cat} bajó {_fmt_pp(dc)}",
                          motivo=f"Margen bruto de {cat}: {_fmt_pct(margin(c_cur))} en {self.month} vs "
                                 f"{_fmt_pct(margin(c_base))} en los 3 meses previos.",
                          indicador="Margen bruto por categoría (pp)", valor_observado=_fmt_pp(dc),
                          umbral=f"≤ -{self.t.category_margin_drop_pp:.1f} pp".replace(".", ","),
                          recomendacion=f"Validar incrementos de costo en {cat} y trasladarlos a precio o negociar "
                                        "con el proveedor.")
        self.evaluations.append(RuleEvaluation(rule, "Alerta" if fired else "Sin alerta",
                                               f"Variación total {_fmt_pp(d)}; {fired} alertas."))

    def rule_low_stock(self) -> None:
        rule = "Inventario bajo"
        if self.snapshots.empty:
            self.evaluations.append(RuleEvaluation(rule, "Sin datos suficientes", "No hay fotos de inventario."))
            return
        cut = pd.Period(self.month, "M").end_time if self.month else None
        snaps = self.snapshots[self.snapshots["fecha_corte"] <= cut] if cut is not None else self.snapshots
        low = op.low_stock(snaps, self.lines)
        for _, r in low.iterrows():
            ratio = r["cantidad"] / r["stock_minimo"] if r["stock_minimo"] else 0
            cover = r.get("dias_cobertura")
            self._add(regla=rule, severidad="Alta" if ratio <= 0.25 else "Media", modulo="Operacional",
                      titulo=f"Inventario bajo: {r['producto']}",
                      motivo=f"Existencias de {int(r['cantidad'])} und al {r['fecha_corte']:%Y-%m-%d}, "
                             f"mínimo definido {int(r['stock_minimo'])} und."
                             + (f" Cobertura estimada: {cover:.0f} días.".replace(".", ",") if cover is not None
                                and pd.notna(cover) else ""),
                      indicador="Existencias vs stock mínimo", valor_observado=f"{int(r['cantidad'])} und",
                      umbral=f"≤ {int(r['stock_minimo'])} und",
                      recomendacion=f"Generar orden de compra por al menos {int(r['faltante_para_minimo'])} und y "
                                    "revisar el punto de reorden del producto.")
        self.evaluations.append(RuleEvaluation(rule, "Alerta" if len(low) else "Sin alerta",
                                               f"{len(low)} productos bajo el mínimo."))

    def rule_concentration(self) -> None:
        rule = "Concentración de ventas"
        recent_months = self._prev_months(2) + ([self.month] if self.month else [])
        recent = self.lines[self.lines["mes"].isin(recent_months)]
        c = concentration(recent, "cliente")
        if c["n"] < self.t.min_customers_concentration:
            self.evaluations.append(RuleEvaluation(
                rule, "Sin datos suficientes",
                f"Se requieren {self.t.min_customers_concentration} clientes con compras; hay {c['n']}."))
            return
        fired = 0
        top_name = c["pareto"].iloc[0]["cliente"]
        if c["top1"] > self.t.top_customer_share_pct:
            fired += 1
            self._add(regla=rule, severidad="Media", modulo="Clientes",
                      titulo=f"Alta dependencia de un cliente: {top_name}",
                      motivo=f"El principal cliente concentra {_fmt_pct(c['top1'])} de las ventas netas de "
                             f"{', '.join(recent_months)}.",
                      indicador="Participación del cliente principal", valor_observado=_fmt_pct(c["top1"]),
                      umbral=f"> {_fmt_pct(self.t.top_customer_share_pct)}",
                      recomendacion="Diversificar la cartera: plan de crecimiento en clientes medianos y "
                                    "condiciones contractuales que reduzcan el riesgo de pérdida.")
        if c["top10"] > self.t.top10_customer_share_pct:
            fired += 1
            self._add(regla=rule, severidad="Media", modulo="Clientes", titulo="Ventas concentradas en 10 clientes",
                      motivo=f"Los 10 principales clientes concentran {_fmt_pct(c['top10'])} de las ventas.",
                      indicador="Participación top 10 clientes", valor_observado=_fmt_pct(c["top10"]),
                      umbral=f"> {_fmt_pct(self.t.top10_customer_share_pct)}",
                      recomendacion="Ampliar la base de clientes activos y monitorear el riesgo de crédito de los "
                                    "principales.")
        self.evaluations.append(RuleEvaluation(rule, "Alerta" if fired else "Sin alerta",
                                               f"Top 1: {_fmt_pct(c['top1'])}; top 10: {_fmt_pct(c['top10'])}; "
                                               f"HHI {c['hhi']:.0f}."))

    def rule_cost_increase(self) -> None:
        rule = "Aumento de costos"
        if self.cost_history.empty or self.month is None:
            self.evaluations.append(RuleEvaluation(rule, "Sin datos suficientes", "No hay historial de costos."))
            return
        ref = pd.Period(self.month, "M").end_time.date()
        first = self.cost_history["fecha_vigencia"].min()
        if pd.Timestamp(ref) - pd.Timedelta(days=90) < first:
            self.evaluations.append(RuleEvaluation(rule, "Sin datos suficientes", "Historial menor a 90 días."))
            return
        ch = op.cost_changes(self.cost_history, ref, 90)
        hits = ch[ch["variacion_pct"].notna() & (ch["variacion_pct"] > self.t.cost_increase_pct)]
        for cat, grp in hits.groupby("categoria"):
            avg = grp["variacion_pct"].mean()
            names = ", ".join(grp["producto"].head(4)) + ("…" if len(grp) > 4 else "")
            self._add(regla=rule, severidad="Alta" if avg > 2 * self.t.cost_increase_pct else "Media",
                      modulo="Operacional", titulo=f"Aumento de costos en {cat} ({len(grp)} productos)",
                      motivo=f"Costo unitario promedio +{_fmt_pct(avg)} en los últimos 90 días. Productos: {names}.",
                      indicador="Variación del costo unitario (90 días)", valor_observado=f"+{_fmt_pct(avg)}",
                      umbral=f"> {_fmt_pct(self.t.cost_increase_pct)}",
                      recomendacion="Negociar con el proveedor, buscar proveedores alternos y evaluar traslado "
                                    "del incremento al precio de venta.")
        self.evaluations.append(RuleEvaluation(rule, "Alerta" if len(hits) else "Sin alerta",
                                               f"{len(hits)} productos con incremento superior al umbral."))

    def rule_opex(self) -> None:
        rule = "Gastos operativos elevados"
        if not self._enough_history(rule):
            return
        if self.expenses is None or self.expenses.empty:
            self.evaluations.append(RuleEvaluation(rule, "Sin datos suficientes", "No hay gastos registrados."))
            return
        prev = self._prev_months(3)
        opex = self.expenses.groupby("mes").monto.sum()
        sales = self.lines.groupby("mes").ventas_netas.sum()
        if self.month not in opex.index or any(p not in opex.index for p in prev):
            self.evaluations.append(RuleEvaluation(rule, "Sin datos suficientes",
                                                   "Faltan gastos registrados en el mes actual o en los previos."))
            return
        ratio = pct(opex[self.month], sales.get(self.month))
        g = growth_pct(opex[self.month], opex[prev].mean())
        fired = 0
        if ratio is not None and ratio > self.t.opex_ratio_pct:
            fired += 1
            self._add(regla=rule, severidad="Alta", modulo="Financiero",
                      titulo=f"Gastos operativos equivalen al {_fmt_pct(ratio)} de las ventas",
                      motivo=f"Gastos de {self.month}: {_fmt_cop(opex[self.month])} sobre ventas netas de "
                             f"{_fmt_cop(sales.get(self.month))}.",
                      indicador="Gastos operativos / ventas netas", valor_observado=_fmt_pct(ratio),
                      umbral=f"> {_fmt_pct(self.t.opex_ratio_pct)}",
                      recomendacion="Revisar presupuesto por centro de gasto y priorizar gastos con retorno medible.")
        if g is not None and g > self.t.opex_increase_pct:
            fired += 1
            by_cat = self.expenses[self.expenses["mes"].isin(prev + [self.month])].groupby(
                ["categoria_gasto", "mes"]).monto.sum().unstack(fill_value=0)
            delta = (by_cat[self.month] - by_cat[prev].mean(axis=1)).sort_values(ascending=False)
            drivers = ", ".join(f"{k} (+{_fmt_cop(v)})" for k, v in delta.head(2).items() if v > 0)
            self._add(regla=rule, severidad="Media", modulo="Financiero",
                      titulo=f"Gastos operativos crecieron {_fmt_pct(g)}",
                      motivo=f"Gastos de {self.month} vs promedio de {', '.join(prev)}. Principales aumentos: "
                             f"{drivers or 'N/D'}.",
                      indicador="Crecimiento de gastos operativos vs promedio 3 meses", valor_observado=_fmt_pct(g),
                      umbral=f"> {_fmt_pct(self.t.opex_increase_pct)}",
                      recomendacion="Validar si el aumento es puntual (campaña, evento) o estructural y medir su "
                                    "impacto en ventas del mes siguiente.")
        self.evaluations.append(RuleEvaluation(rule, "Alerta" if fired else "Sin alerta",
                                               f"Gasto/ventas {_fmt_pct(ratio)}; crecimiento {_fmt_pct(g)}."))

    # -------------------------------------------------------------- ejecutar
    def run(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self.month is None:
            ev = pd.DataFrame([asdict(RuleEvaluation("Todas", "Sin datos suficientes", "No hay ventas registradas."))])
            return pd.DataFrame(columns=list(Alert.__dataclass_fields__)), ev
        for rule in (self.rule_sales_drop, self.rule_region_drop, self.rule_margin_drop, self.rule_low_stock,
                     self.rule_concentration, self.rule_cost_increase, self.rule_opex):
            try:
                rule()
            except Exception as exc:  # una regla con error no debe bloquear las demás
                self.evaluations.append(RuleEvaluation(rule.__name__, "Error", str(exc)))
        alerts = pd.DataFrame([asdict(a) for a in self.alerts], columns=list(Alert.__dataclass_fields__))
        if not alerts.empty:
            alerts = alerts.sort_values("severidad", key=lambda s: s.map(SEVERITY_ORDER)).reset_index(drop=True)
        return alerts, pd.DataFrame([asdict(e) for e in self.evaluations])


def evaluate_alerts(lines: pd.DataFrame, expenses: pd.DataFrame, snapshots: pd.DataFrame,
                    cost_history: pd.DataFrame, thresholds: AlertThresholds | None = None,
                    end_month: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    engine = AlertEngine(lines, expenses, snapshots, cost_history, thresholds, end_month)
    alerts, evaluations = engine.run()
    return alerts, evaluations, engine.month


__all__ = ["Alert", "AlertEngine", "evaluate_alerts", "last_complete_month"]
