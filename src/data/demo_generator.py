"""Generador de datos sintéticos (DEMO) para una distribuidora comercial colombiana ficticia.

Todos los nombres, códigos y cifras son inventados. Los códigos llevan el
prefijo ``DEMO`` y la columna ``origen`` de cada tabla se marca como ``DEMO``.
Las regiones y ciudades son geografía real de Colombia, no datos de empresas.

El generador es determinista (semilla fija) y produce información coherente:
  * Ventas con estacionalidad, tendencia, descuentos y devoluciones.
  * Historial de costos con inflación y un choque de costos controlado.
  * Compras que reabastecen la demanda, con retrasos y entregas parciales.
  * Kardex (movimientos) y fotos de inventario de fin de mes que cuadran entre sí.
  * Gastos operativos mensuales por categoría.

Escenarios incorporados para la demostración del centro de alertas
(último mes del horizonte):
  * Caída de ventas en la región Caribe (problema logístico simulado).
  * Aumento de costo en Lácteos y aceites sin ajuste de precio (presión de margen).
  * Campaña de marketing que eleva los gastos operativos.
  * Productos con inventario por debajo del mínimo y productos descontinuados sin movimiento.
"""
from __future__ import annotations

import calendar
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from sqlalchemy import Engine

from src.database import models as m

REGIONS = [
    ("AND", "Andina", "Bogotá", ["Bogotá", "Soacha", "Chía", "Tunja"], 0.30),
    ("ANT", "Antioquia", "Medellín", ["Medellín", "Envigado", "Bello", "Rionegro"], 0.20),
    ("CAR", "Caribe", "Barranquilla", ["Barranquilla", "Cartagena", "Santa Marta", "Soledad"], 0.17),
    ("PAC", "Pacífico", "Cali", ["Cali", "Palmira", "Jamundí", "Tuluá"], 0.15),
    ("CAF", "Eje Cafetero", "Pereira", ["Pereira", "Manizales", "Armenia"], 0.09),
    ("SAN", "Santanderes", "Bucaramanga", ["Bucaramanga", "Floridablanca", "Cúcuta"], 0.09),
]

SELLER_NAMES = ["Laura M.", "Andrés P.", "Camila R.", "Julián T.", "Valentina G.", "Santiago L.",
                "Daniela C.", "Felipe O.", "Mariana S.", "Sebastián V.", "Natalia H.", "Mateo B."]

SUPPLIERS = [
    ("DEMO-PRV-01", "Proveedor DEMO Alfa Alimentos", "Bogotá", 30, 5),
    ("DEMO-PRV-02", "Proveedor DEMO Beta Bebidas", "Medellín", 45, 6),
    ("DEMO-PRV-03", "Proveedor DEMO Gamma Hogar", "Cali", 30, 8),
    ("DEMO-PRV-04", "Proveedor DEMO Delta Cuidado", "Bogotá", 60, 7),
    ("DEMO-PRV-05", "Proveedor DEMO Épsilon Snacks", "Barranquilla", 30, 6),
    ("DEMO-PRV-06", "Proveedor DEMO Zeta Lácteos", "Pereira", 15, 3),
    ("DEMO-PRV-07", "Proveedor DEMO Eta Empaques", "Bucaramanga", 30, 9),
    ("DEMO-PRV-08", "Proveedor DEMO Theta Granos", "Bogotá", 30, 6),
]

# categoría -> (descripción, [(nombre, unidad, costo base COP, popularidad, proveedor)])
CATALOG: dict[str, tuple[str, list[tuple[str, str, int, float, int]]]] = {
    "Abarrotes": ("Granos, aceites y básicos de despensa", [
        ("Arroz blanco 500 g", "UND", 1900, 1.6, 8), ("Arroz blanco 5 kg", "UND", 17500, 1.0, 8),
        ("Azúcar 1 kg", "UND", 3600, 1.4, 8), ("Aceite vegetal 1 L", "UND", 7800, 1.3, 1),
        ("Aceite vegetal 3 L", "UND", 21000, 0.7, 1), ("Pasta spaghetti 500 g", "UND", 2900, 1.2, 1),
        ("Lenteja 500 g", "UND", 3300, 0.8, 8), ("Fríjol rojo 500 g", "UND", 4800, 0.8, 8),
        ("Sal refinada 1 kg", "UND", 1400, 0.9, 1), ("Harina de trigo 1 kg", "UND", 3200, 0.6, 1),
        ("Café molido 500 g", "UND", 15500, 1.0, 1), ("Chocolate de mesa 500 g", "UND", 9800, 0.7, 1),
    ]),
    "Bebidas": ("Bebidas no alcohólicas", [
        ("Gaseosa 1,5 L", "UND", 3900, 1.5, 2), ("Agua sin gas 600 ml", "UND", 1100, 1.3, 2),
        ("Jugo néctar 1 L", "UND", 3700, 0.9, 2), ("Bebida hidratante 500 ml", "UND", 2600, 0.8, 2),
        ("Té frío 1,5 L", "UND", 4200, 0.5, 2), ("Agua sin gas 6 L", "UND", 5800, 0.6, 2),
    ]),
    "Aseo del hogar": ("Limpieza y cuidado del hogar", [
        ("Detergente en polvo 1 kg", "UND", 8900, 1.2, 3), ("Lavaloza en crema 500 g", "UND", 3900, 1.0, 3),
        ("Limpiador multiusos 1 L", "UND", 5200, 0.7, 3), ("Blanqueador 1 L", "UND", 2900, 0.9, 3),
        ("Suavizante de ropa 1 L", "UND", 6900, 0.6, 3), ("Papel higiénico x12", "PAQ", 16500, 1.1, 3),
        ("Toallas de cocina x3", "PAQ", 7900, 0.5, 3), ("Bolsas de basura x10", "PAQ", 3600, 0.15, 3),
    ]),
    "Cuidado personal": ("Higiene y cuidado personal", [
        ("Shampoo 400 ml", "UND", 11800, 0.7, 4), ("Jabón de tocador x3", "PAQ", 6200, 0.9, 4),
        ("Crema dental 100 ml", "UND", 4300, 1.0, 4), ("Desodorante 150 ml", "UND", 9900, 0.6, 4),
        ("Toallas higiénicas x10", "PAQ", 4800, 0.7, 4), ("Pañales etapa 3 x30", "PAQ", 36000, 0.5, 4),
    ]),
    "Snacks y confitería": ("Pasabocas, galletas y dulces", [
        ("Papas fritas 150 g", "UND", 4200, 1.1, 5), ("Galletas surtidas 300 g", "UND", 4900, 0.9, 5),
        ("Chocolatina 40 g", "UND", 1500, 1.0, 5), ("Maní salado 200 g", "UND", 3900, 0.5, 5),
        ("Gomitas 100 g", "UND", 1900, 0.5, 5), ("Barra de cereal x6", "PAQ", 6800, 0.12, 5),
    ]),
    "Lácteos y refrigerados": ("Lácteos, huevos y refrigerados", [
        ("Leche entera 1 L", "UND", 3500, 1.6, 6), ("Leche UHT x6", "PAQ", 19800, 0.8, 6),
        ("Yogur 1 L", "UND", 6500, 0.8, 6), ("Queso campesino 500 g", "UND", 11500, 0.7, 6),
        ("Mantequilla 250 g", "UND", 7200, 0.5, 6), ("Huevos x30", "PAQ", 15800, 1.2, 6),
    ]),
    "Desechables": ("Desechables y empaques", [
        ("Vasos desechables x50", "PAQ", 4900, 0.6, 7), ("Platos desechables x20", "PAQ", 3900, 0.5, 7),
        ("Servilletas x300", "PAQ", 4200, 0.6, 7), ("Papel aluminio 7 m", "UND", 5100, 0.3, 7),
        ("Contenedores x25", "PAQ", 8900, 0.10, 7),
    ]),
}

DISCONTINUED = {"Té frío 1,5 L", "Gomitas 100 g"}          # dejan de venderse: sin movimiento
COST_SHOCK_CATEGORIES = {"Lácteos y refrigerados"}           # choque de costo al final del horizonte
COST_SHOCK_PRODUCTS = {"Aceite vegetal 1 L", "Aceite vegetal 3 L"}
LOW_STOCK_PRODUCTS = {"Arroz blanco 500 g", "Detergente en polvo 1 kg", "Gaseosa 1,5 L",
                      "Crema dental 100 ml", "Huevos x30"}
SHOCK_REGION = "Caribe"

CUSTOMER_TYPES = [  # (tipo, prefijo, peso de frecuencia, factor de tamaño de pedido, descuento máx)
    ("Tienda de barrio", "Tienda", 0.45, 1.0, 0.03),
    ("Minimercado", "Minimercado", 0.25, 2.2, 0.05),
    ("Supermercado independiente", "Supermercado", 0.10, 5.0, 0.08),
    ("HORECA", "Restaurante", 0.12, 2.0, 0.05),
    ("Institucional", "Casino empresarial", 0.08, 3.5, 0.10),
]
FANTASY = ["La Esquina", "El Progreso", "San José", "La Económica", "El Ahorro", "Los Andes", "La Bendición",
           "El Triunfo", "La Fortuna", "Villa Nueva", "El Portal", "La Estrella", "Santa Fe", "El Edén",
           "La Colina", "Primavera", "El Sol", "La Pradera", "Buenavista", "El Recreo"]

SEASONALITY = {1: 0.88, 2: 0.92, 3: 0.98, 4: 0.97, 5: 1.00, 6: 1.02, 7: 1.00, 8: 1.01, 9: 1.00,
               10: 1.03, 11: 1.08, 12: 1.22}
CHANNELS = [("Preventa", 0.62), ("Televenta", 0.23), ("Comercio electrónico B2B", 0.15)]

EXPENSE_SHARES = {  # % de las ventas netas de referencia
    "Nómina administrativa y comercial": 0.090,
    "Arriendo de bodegas y oficinas": 0.030,
    "Transporte y logística": 0.035,
    "Servicios públicos": 0.008,
    "Marketing y publicidad": 0.012,
    "Tecnología y software": 0.006,
    "Gastos administrativos": 0.014,
}
REGIONAL_EXPENSES = {"Nómina administrativa y comercial", "Transporte y logística"}


@dataclass(frozen=True)
class DemoConfig:
    start: date = date(2025, 1, 1)
    end: date = date(2026, 10, 31)
    n_customers: int = 180
    invoices_per_month: int = 270
    seed: int = 2026
    scenarios: bool = True


def month_starts(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while d <= end:
        out.append(d)
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def round_to(value: float, step: int = 50) -> int:
    return int(max(step, round(value / step) * step))


class _Schedule:
    """Serie escalonada (fecha de vigencia -> valor) con consulta por fecha."""

    def __init__(self) -> None:
        self.dates: list[date] = []
        self.values: list[int] = []

    def add(self, d: date, v: int) -> None:
        self.dates.append(d)
        self.values.append(v)

    def at(self, d: date) -> int:
        i = bisect_right(self.dates, d) - 1
        return self.values[max(i, 0)]


def generate(cfg: DemoConfig = DemoConfig()) -> dict[str, list[dict]]:
    """Devuelve un diccionario tabla -> lista de registros listos para insertar."""
    rng = np.random.default_rng(cfg.seed)
    months = month_starts(cfg.start, cfg.end)
    last_month = months[-1]
    data: dict[str, list[dict]] = defaultdict(list)

    # ------------------------------------------------------------------ maestros
    region_ids = {}
    for i, (code, name, city, _cities, _w) in enumerate(REGIONS, start=1):
        region_ids[name] = i
        data["regiones"].append({"id": i, "codigo": code, "nombre": name, "ciudad_principal": city})

    sellers_by_region: dict[int, list[int]] = defaultdict(list)
    for i, seller in enumerate(SELLER_NAMES, start=1):
        rid = (i - 1) // 2 + 1
        sellers_by_region[rid].append(i)
        data["vendedores"].append({
            "id": i, "codigo": f"DEMO-VEN-{i:02d}", "nombre": f"{seller} (DEMO)", "region_id": rid,
            "fecha_ingreso": date(2022 + i % 3, 1 + i % 12, 1), "activo": True, "origen": "DEMO"})

    for i, (code, name, city, terms, lead) in enumerate(SUPPLIERS, start=1):
        data["proveedores"].append({"id": i, "codigo": code, "nombre": name, "ciudad": city,
                                    "plazo_pago_dias": terms, "lead_time_dias": lead, "origen": "DEMO"})
    lead_times = {i: s[4] for i, s in enumerate(SUPPLIERS, start=1)}

    products: list[dict] = []
    pid = 0
    for cid, (cat, (desc, items)) in enumerate(CATALOG.items(), start=1):
        data["categorias"].append({"id": cid, "nombre": cat, "descripcion": desc})
        for name, unit, cost, pop, sup in items:
            pid += 1
            products.append({"id": pid, "sku": f"DEMO-{cid:02d}{pid:03d}", "nombre": name, "categoria": cat,
                             "categoria_id": cid, "proveedor_id": sup, "unidad": unit, "base_cost": cost,
                             "pop": pop, "markup": float(rng.uniform(1.24, 1.40))})

    # ------------------------------------------------- historial de costos/precios
    shock_date = months[-1]
    cost_sched: dict[int, _Schedule] = {}
    price_sched: dict[int, _Schedule] = {}
    for p in products:
        cs, ps = _Schedule(), _Schedule()
        cost = p["base_cost"]
        cs.add(date(cfg.start.year - 1, 12, 31), cost)
        ps.add(date(cfg.start.year - 1, 12, 31), round_to(cost * p["markup"]))
        data["costos"].append({"producto_id": p["id"], "fecha_vigencia": cs.dates[0], "costo_unitario": cost,
                               "motivo": "Costo inicial"})
        offset = int(rng.integers(0, 4))
        for k, ms in enumerate(months):
            shocked = cfg.scenarios and ms == shock_date and (
                p["categoria"] in COST_SHOCK_CATEGORIES or p["nombre"] in COST_SHOCK_PRODUCTS)
            if shocked:
                cost = int(round(cost * rng.uniform(1.11, 1.16)))
                cs.add(ms, cost)
                data["costos"].append({"producto_id": p["id"], "fecha_vigencia": ms, "costo_unitario": cost,
                                       "motivo": "Ajuste de proveedor (DEMO)"})
                continue  # el precio de venta NO se ajusta: presión de margen
            if (k + offset) % 4 == 0 and k > 0:
                cost = int(round(cost * rng.uniform(1.008, 1.025)))
                cs.add(ms, cost)
                data["costos"].append({"producto_id": p["id"], "fecha_vigencia": ms, "costo_unitario": cost,
                                       "motivo": "Actualización por inflación (DEMO)"})
                lag = ms + timedelta(days=int(rng.integers(10, 35)))
                ps.add(lag, round_to(cost * p["markup"]))
        cost_sched[p["id"]], price_sched[p["id"]] = cs, ps

    # ------------------------------------------------------------------ clientes
    customers = []
    type_p = np.array([t[2] for t in CUSTOMER_TYPES])
    region_p = np.array([r[4] for r in REGIONS])
    horizon_days = (cfg.end - cfg.start).days
    for i in range(1, cfg.n_customers + 1):
        t = CUSTOMER_TYPES[int(rng.choice(len(CUSTOMER_TYPES), p=type_p / type_p.sum()))]
        r = REGIONS[int(rng.choice(len(REGIONS), p=region_p / region_p.sum()))]
        joined = (cfg.start - timedelta(days=int(rng.integers(30, 900)))) if rng.random() < 0.72 else \
            cfg.start + timedelta(days=int(rng.integers(0, max(horizon_days - 20, 1))))
        churn = None
        if rng.random() < 0.13:
            churn = cfg.start + timedelta(days=int(rng.integers(120, max(horizon_days - 60, 121))))
        weight = float(rng.lognormal(0, 0.55)) * t[3] ** 0.8
        name = f"{t[1]} {FANTASY[i % len(FANTASY)]} DEMO-{i:03d}"
        if i == 1:  # cliente ancla (cadena regional) para ilustrar concentración de ingresos
            t, r, joined, churn, weight = CUSTOMER_TYPES[2], REGIONS[0], date(2021, 3, 1), None, 0.0
            name = "Cadena Regional DEMO-001"
        customers.append({"id": i, "tipo": t[0], "size": t[3], "max_disc": t[4], "region": r[1],
                          "joined": joined, "churn": churn, "weight": weight})
        data["clientes"].append({"id": i, "codigo": f"DEMO-CLI-{i:03d}", "nombre": name, "tipo": t[0],
                                 "region_id": region_ids[r[1]], "ciudad": str(rng.choice(r[3])),
                                 "fecha_registro": joined, "origen": "DEMO"})
    total_w = sum(c["weight"] for c in customers[1:])
    customers[0]["weight"] = total_w * 0.035   # frecuencia alta + pedidos grandes => ~10-12 % de ingresos
    customers[0]["size"] = 9.0

    # -------------------------------------------------------------------- ventas
    pop = np.array([p["pop"] for p in products])
    sold_net = defaultdict(int)          # (producto_id, mes) -> unidades netas vendidas
    sale_id = line_id = 0
    for k, ms in enumerate(months):
        me = min(month_end(ms), cfg.end)
        n_inv = cfg.invoices_per_month * SEASONALITY[ms.month] * (1 + 0.008 * k) * rng.normal(1, 0.03)
        active = [c for c in customers if c["joined"] <= me and (c["churn"] is None or c["churn"] > ms)]
        if not active:
            continue
        weights = []
        for c in active:
            w = c["weight"]
            if cfg.scenarios and ms == last_month and c["region"] == SHOCK_REGION:
                w *= 0.55
            weights.append(w)
        wp = np.array(weights) / sum(weights)
        picks = rng.choice(len(active), size=max(int(n_inv), 1), p=wp)
        days_in_month = (me - ms).days + 1
        prod_ok = np.array([0.0 if (cfg.scenarios and p["nombre"] in DISCONTINUED and ms >= date(2026, 6, 1))
                            else 1.0 for p in products])
        pp = pop * prod_ok
        pp = pp / pp.sum()
        for ci in picks:
            c = active[int(ci)]
            d = ms + timedelta(days=int(rng.integers(0, days_in_month)))
            if d.weekday() == 6:  # domingo -> lunes (o sábado si se sale del mes)
                d = d + timedelta(days=1) if d + timedelta(days=1) <= me else d - timedelta(days=1)
            if d < c["joined"]:
                d = c["joined"] if c["joined"] <= me else me
            region = c["region"]
            rid = region_ids[region]
            sale_id += 1
            data["ventas"].append({
                "id": sale_id, "numero_factura": f"DEMO-FV-{sale_id:06d}", "fecha": d, "cliente_id": c["id"],
                "vendedor_id": int(rng.choice(sellers_by_region[rid])), "region_id": rid,
                "canal": CHANNELS[int(rng.choice(3, p=[x[1] for x in CHANNELS]))][0], "origen": "DEMO"})
            n_lines = int(min(1 + rng.poisson(2.6 + c["size"] * 0.25), 9))
            chosen = rng.choice(len(products), size=min(n_lines, int((pp > 0).sum())), replace=False, p=pp)
            for pi in chosen:
                p = products[int(pi)]
                qty_scale = 24 if p["base_cost"] < 6000 else (12 if p["base_cost"] < 15000 else 6)
                qty = int(1 + rng.poisson(c["size"] * qty_scale))
                price = price_sched[p["id"]].at(d)
                gross = qty * price
                disc = 0
                if rng.random() < 0.35:
                    disc = int(round(gross * rng.uniform(0.01, c["max_disc"])))
                returned = int(rng.integers(1, max(2, qty // 3 + 1))) if rng.random() < 0.03 else 0
                returned = min(returned, qty)
                line_id += 1
                data["detalle_ventas"].append({
                    "id": line_id, "venta_id": sale_id, "producto_id": p["id"], "cantidad": qty,
                    "precio_unitario": price, "descuento": disc, "cantidad_devuelta": returned,
                    "costo_unitario": cost_sched[p["id"]].at(d)})
                data["movimientos_inventario"].append({
                    "producto_id": p["id"], "fecha": d, "tipo": "SALIDA_VENTA", "cantidad": -qty,
                    "costo_unitario": cost_sched[p["id"]].at(d), "referencia": f"DEMO-FV-{sale_id:06d}"})
                if returned:
                    rd = min(d + timedelta(days=int(rng.integers(1, 8))), me)
                    data["movimientos_inventario"].append({
                        "producto_id": p["id"], "fecha": rd, "tipo": "DEVOLUCION_CLIENTE", "cantidad": returned,
                        "costo_unitario": cost_sched[p["id"]].at(d), "referencia": f"DEMO-FV-{sale_id:06d}"})
                sold_net[(p["id"], ms)] += qty - returned

    # ------------------------------------------- compras, kardex e inventario
    opening_date = date(cfg.start.year - 1, 12, 31)
    stock: dict[int, int] = {}
    stock_min: dict[int, int] = {}
    for p in products:
        demand = [sold_net[(p["id"], ms)] for ms in months[:3]] or [0]
        avg = max(1, int(np.mean(demand)))
        stock_min[p["id"]] = max(5, int(avg * 0.35))
        stock[p["id"]] = int(avg * rng.uniform(1.1, 1.6))
        c0 = cost_sched[p["id"]].at(opening_date)
        data["movimientos_inventario"].append({"producto_id": p["id"], "fecha": opening_date,
                                               "tipo": "INVENTARIO_INICIAL", "cantidad": stock[p["id"]],
                                               "costo_unitario": c0, "referencia": "DEMO-SALDO-INICIAL"})
        data["inventario"].append({"producto_id": p["id"], "fecha_corte": opening_date, "cantidad": stock[p["id"]],
                                   "costo_unitario": c0, "valor": stock[p["id"]] * c0})

    order_id = pline_id = 0
    for k, ms in enumerate(months):
        me = min(month_end(ms), cfg.end)
        by_supplier: dict[int, list[dict]] = defaultdict(list)
        for p in products:
            demand = sold_net[(p["id"], ms)]
            opening = stock[p["id"]]
            if cfg.scenarios and p["nombre"] in DISCONTINUED and ms >= date(2026, 6, 1):
                received = 0  # descontinuado: no se repone
                ordered = 0
            else:
                target = demand * rng.uniform(1.05, 1.25) + stock_min[p["id"]] * 1.3
                ordered = max(0, int(round(target - opening)))
                received = ordered if rng.random() < 0.88 else int(ordered * rng.uniform(0.80, 0.96))
                if cfg.scenarios and ms == last_month and p["nombre"] in LOW_STOCK_PRODUCTS:
                    received = max(0, demand - opening + int(rng.integers(0, max(1, stock_min[p["id"]] // 2))))
                    ordered = max(ordered, received)
            if opening + received - demand < 0:          # nunca stock negativo
                received = demand - opening
                ordered = max(ordered, received)
            stock[p["id"]] = opening + received - demand
            if ordered > 0:
                by_supplier[p["proveedor_id"]].append({"p": p, "ordered": ordered, "received": received})
            c_me = cost_sched[p["id"]].at(me)
            data["inventario"].append({"producto_id": p["id"], "fecha_corte": me, "cantidad": stock[p["id"]],
                                       "costo_unitario": c_me, "valor": stock[p["id"]] * c_me})
        for sup, lines in by_supplier.items():
            order_id += 1
            od = ms + timedelta(days=int(rng.integers(0, 4)))
            expected = od + timedelta(days=lead_times[sup])
            delay = int(rng.integers(2, 7)) if rng.random() < 0.18 else int(rng.integers(-1, 1))
            if cfg.scenarios and ms == last_month and sup == 6:
                delay = int(rng.integers(4, 8))
            rec = max(od, min(expected + timedelta(days=delay), me))
            partial = any(ln["received"] < ln["ordered"] for ln in lines)
            data["compras"].append({"id": order_id, "numero_orden": f"DEMO-OC-{order_id:05d}", "proveedor_id": sup,
                                    "fecha_orden": od, "fecha_esperada": expected, "fecha_recepcion": rec,
                                    "estado": "PARCIAL" if partial else "RECIBIDA", "origen": "DEMO"})
            for ln in lines:
                pline_id += 1
                cu = cost_sched[ln["p"]["id"]].at(od)
                data["detalle_compras"].append({"id": pline_id, "compra_id": order_id, "producto_id": ln["p"]["id"],
                                                "cantidad_pedida": ln["ordered"], "cantidad_recibida": ln["received"],
                                                "costo_unitario": cu})
                if ln["received"] > 0:
                    data["movimientos_inventario"].append({
                        "producto_id": ln["p"]["id"], "fecha": rec, "tipo": "ENTRADA_COMPRA",
                        "cantidad": ln["received"], "costo_unitario": cu, "referencia": f"DEMO-OC-{order_id:05d}"})
    # Orden abierta al cierre (pendiente de recepción): ilustra el manejo de datos incompletos.
    order_id += 1
    od = max(cfg.end - timedelta(days=3), months[-1])
    data["compras"].append({"id": order_id, "numero_orden": f"DEMO-OC-{order_id:05d}", "proveedor_id": 1,
                            "fecha_orden": od, "fecha_esperada": od + timedelta(days=lead_times[1]),
                            "fecha_recepcion": None, "estado": "PENDIENTE", "origen": "DEMO"})
    for p in [p for p in products if p["proveedor_id"] == 1][:4]:
        pline_id += 1
        data["detalle_compras"].append({"id": pline_id, "compra_id": order_id, "producto_id": p["id"],
                                        "cantidad_pedida": 200, "cantidad_recibida": 0,
                                        "costo_unitario": cost_sched[p["id"]].at(od)})

    # ------------------------------------------------------- productos (final)
    for p in products:
        last_cost = cost_sched[p["id"]].values[-1]
        data["productos"].append({
            "id": p["id"], "sku": p["sku"], "nombre": p["nombre"], "categoria_id": p["categoria_id"],
            "proveedor_id": p["proveedor_id"], "unidad": p["unidad"], "precio_lista": price_sched[p["id"]].values[-1],
            "costo_unitario": last_cost, "stock_minimo": stock_min[p["id"]], "activo": True, "origen": "DEMO"})

    # ------------------------------------------------------------ gastos
    ref_sales = defaultdict(int)
    by_region_month = defaultdict(int)
    sale_region = {v["id"]: v["region_id"] for v in data["ventas"]}
    sale_month = {v["id"]: date(v["fecha"].year, v["fecha"].month, 1) for v in data["ventas"]}
    for ln in data["detalle_ventas"]:
        gross = ln["cantidad"] * ln["precio_unitario"] - ln["descuento"]
        by_region_month[(sale_region[ln["venta_id"]], sale_month[ln["venta_id"]])] += gross
        ref_sales[sale_month[ln["venta_id"]]] += gross
    base_month_sales = float(np.mean([ref_sales[ms] for ms in months[:3]]))
    for k, ms in enumerate(months):
        growth = (1.09 ** (ms.year - cfg.start.year))  # incremento salarial/arriendos anual
        for cat, share in EXPENSE_SHARES.items():
            if cat == "Transporte y logística":
                base = ref_sales[ms] * share          # variable con la venta
            else:
                base = base_month_sales * share * growth
            base *= rng.normal(1, 0.03)
            if cfg.scenarios and ms == last_month and cat == "Marketing y publicidad":
                base *= 3.6                          # campaña de temporada
            if cfg.scenarios and ms == last_month and cat == "Transporte y logística":
                base *= 1.25                         # sobrecostos logísticos
            day = min(28, 5 + list(EXPENSE_SHARES).index(cat) * 3)
            fecha = min(date(ms.year, ms.month, day), cfg.end)
            if cat in REGIONAL_EXPENSES:
                total_rm = sum(by_region_month[(rid, ms)] for rid in region_ids.values()) or 1
                for rname, rid in region_ids.items():
                    amount = int(round(base * by_region_month[(rid, ms)] / total_rm))
                    if amount > 0:
                        data["gastos_operativos"].append({"fecha": fecha, "categoria_gasto": cat, "region_id": rid,
                                                          "descripcion": f"{cat} - {rname} (DEMO)",
                                                          "monto": amount, "origen": "DEMO"})
            else:
                data["gastos_operativos"].append({"fecha": fecha, "categoria_gasto": cat, "region_id": None,
                                                  "descripcion": f"{cat} - corporativo (DEMO)",
                                                  "monto": int(round(base)), "origen": "DEMO"})
    return dict(data)


INSERT_ORDER = ["regiones", "vendedores", "categorias", "proveedores", "productos", "clientes", "costos",
                "ventas", "detalle_ventas", "compras", "detalle_compras", "inventario",
                "movimientos_inventario", "gastos_operativos"]


def load_demo(engine: Engine, cfg: DemoConfig = DemoConfig(), reset: bool = True) -> dict[str, int]:
    """Genera e inserta los datos DEMO. Con ``reset=True`` reconstruye el esquema primero."""
    from src.database.connection import init_db

    init_db(engine, drop=reset)
    data = generate(cfg)
    tables = m.Base.metadata.tables
    counts = {}
    with engine.begin() as conn:
        for name in INSERT_ORDER:
            rows = data.get(name, [])
            if rows:
                for i in range(0, len(rows), 5000):
                    conn.execute(tables[name].insert(), rows[i:i + 5000])
            counts[name] = len(rows)
    return counts
