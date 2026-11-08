"""Controles de calidad sobre los datos ya cargados en la base."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, text

from src.database.connection import get_engine

CHECKS = [
    ("Integridad referencial (llaves foráneas)", "SELECT COUNT(*) FROM pragma_foreign_key_check", "= 0"),
    ("Facturas sin líneas de detalle",
     "SELECT COUNT(*) FROM ventas v WHERE NOT EXISTS (SELECT 1 FROM detalle_ventas d WHERE d.venta_id = v.id)", "= 0"),
    ("Líneas de venta con precio inferior al costo",
     "SELECT COUNT(*) FROM detalle_ventas WHERE precio_unitario < costo_unitario", "informativo"),
    ("Líneas con descuento superior al 20 % del valor bruto",
     "SELECT COUNT(*) FROM detalle_ventas WHERE descuento > 0.2 * cantidad * precio_unitario", "informativo"),
    ("Clientes sin compras",
     "SELECT COUNT(*) FROM clientes c WHERE NOT EXISTS (SELECT 1 FROM ventas v WHERE v.cliente_id = c.id)",
     "informativo"),
    ("Productos sin historial de costo",
     "SELECT COUNT(*) FROM productos p WHERE NOT EXISTS (SELECT 1 FROM costos c WHERE c.producto_id = p.id)", "= 0"),
    ("Órdenes de compra pendientes de recepción", "SELECT COUNT(*) FROM compras WHERE fecha_recepcion IS NULL",
     "informativo"),
    ("Productos cuyo kardex no cuadra con la última foto de inventario", """
        SELECT COUNT(*) FROM (
          SELECT p.id, COALESCE((SELECT SUM(m.cantidad) FROM movimientos_inventario m WHERE m.producto_id = p.id), 0)
                 AS saldo,
                 (SELECT i.cantidad FROM inventario i WHERE i.producto_id = p.id ORDER BY i.fecha_corte DESC LIMIT 1)
                 AS foto
          FROM productos p) t
        WHERE t.foto IS NOT NULL AND t.saldo <> t.foto""", "= 0"),
    ("Ventas importadas (no afectan el kardex en v1)", "SELECT COUNT(*) FROM ventas WHERE origen <> 'DEMO'",
     "informativo"),
]


def run_quality_checks(engine: Engine | None = None) -> pd.DataFrame:
    rows = []
    with (engine or get_engine()).connect() as conn:
        for name, sql, expected in CHECKS:
            try:
                value = int(conn.execute(text(sql)).scalar() or 0)
                if expected == "= 0":
                    status = "OK" if value == 0 else "Revisar"
                else:
                    status = "Informativo"
            except Exception as exc:  # p. ej. motor sin soporte de pragma
                value, status = None, f"Error: {exc}"
            rows.append({"control": name, "resultado": value, "esperado": expected, "estado": status})
    return pd.DataFrame(rows)
