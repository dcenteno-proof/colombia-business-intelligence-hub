"""Genera sql/schema.sql y docs/diccionario_datos.md a partir de los modelos SQLAlchemy.

Así el DDL y el diccionario de datos siempre coinciden con el código.
Uso:  python scripts/generate_schema_docs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from src.database.models import Base  # noqa: E402

TABLE_DESC = {
    "regiones": "Regiones comerciales de Colombia donde opera la distribuidora.",
    "vendedores": "Fuerza de ventas, asignada a una región.",
    "categorias": "Categorías de producto.",
    "proveedores": "Proveedores de mercancía, con condiciones de pago y tiempo de entrega.",
    "productos": "Maestro de productos (SKU) con precio de lista y costo vigentes.",
    "clientes": "Maestro de clientes (tiendas, minimercados, HORECA, institucionales).",
    "ventas": "Encabezado de factura de venta.",
    "detalle_ventas": "Líneas de factura: cantidades, precio, descuento, devoluciones y costo a la fecha.",
    "compras": "Órdenes de compra a proveedores.",
    "detalle_compras": "Líneas de orden de compra: unidades pedidas y recibidas.",
    "inventario": "Foto del inventario al cierre de cada mes, por producto.",
    "movimientos_inventario": "Kardex: entradas (+) y salidas (-) de unidades por producto.",
    "gastos_operativos": "Gastos operativos por categoría, región (opcional) y fecha.",
    "costos": "Historial del costo unitario por producto (vigencia desde una fecha).",
    "registro_importaciones": "Bitácora del proceso ETL (un registro por archivo importado).",
}

COL_DESC = {
    "id": "Identificador interno (llave primaria).",
    "codigo": "Código de negocio único.",
    "nombre": "Nombre descriptivo.",
    "ciudad_principal": "Ciudad principal de la región.",
    "region_id": "Región asociada (FK regiones.id).",
    "fecha_ingreso": "Fecha de ingreso del vendedor.",
    "activo": "Indicador de registro activo.",
    "origen": "Procedencia del dato: 'DEMO' o 'IMPORTACION:<archivo>'.",
    "descripcion": "Descripción libre.",
    "ciudad": "Ciudad.",
    "plazo_pago_dias": "Plazo de pago acordado (días).",
    "lead_time_dias": "Tiempo de entrega pactado (días).",
    "sku": "Código único del producto.",
    "categoria_id": "Categoría (FK categorias.id).",
    "proveedor_id": "Proveedor (FK proveedores.id).",
    "unidad": "Unidad de venta (UND, PAQ).",
    "precio_lista": "Precio de lista vigente, COP entero.",
    "costo_unitario": "Costo unitario en COP entero (en detalle: costo vigente a la fecha de la transacción).",
    "stock_minimo": "Existencia mínima objetivo (unidades).",
    "tipo": "Tipo de cliente.",
    "fecha_registro": "Fecha de vinculación del cliente.",
    "numero_factura": "Número de factura único.",
    "fecha": "Fecha de la transacción.",
    "cliente_id": "Cliente (FK clientes.id).",
    "vendedor_id": "Vendedor (FK vendedores.id), opcional.",
    "canal": "Canal de venta.",
    "venta_id": "Factura (FK ventas.id).",
    "producto_id": "Producto (FK productos.id).",
    "cantidad": "Unidades (en kardex con signo: + entrada, - salida).",
    "precio_unitario": "Precio unitario facturado, COP entero.",
    "descuento": "Descuento total de la línea, COP entero (0 ≤ descuento ≤ cantidad × precio).",
    "cantidad_devuelta": "Unidades devueltas por el cliente (0 ≤ devueltas ≤ cantidad).",
    "numero_orden": "Número de orden de compra único.",
    "fecha_orden": "Fecha de emisión de la orden.",
    "fecha_esperada": "Fecha comprometida de entrega.",
    "fecha_recepcion": "Fecha real de recepción (nula si está pendiente).",
    "estado": "Estado del registro.",
    "compra_id": "Orden de compra (FK compras.id).",
    "cantidad_pedida": "Unidades pedidas.",
    "cantidad_recibida": "Unidades efectivamente recibidas.",
    "fecha_corte": "Fecha de corte (cierre de mes) de la foto de inventario.",
    "valor": "Valor del inventario al costo = cantidad × costo_unitario (COP).",
    "tipo_gasto": "Tipo de gasto.",
    "categoria_gasto": "Categoría del gasto operativo.",
    "monto": "Importe del gasto, COP entero (> 0).",
    "referencia": "Documento origen del movimiento (factura u orden).",
    "fecha_vigencia": "Fecha desde la cual aplica el costo.",
    "motivo": "Motivo del cambio de costo.",
    "archivo": "Nombre del archivo importado.",
    "entidad": "Tipo de información importada.",
    "filas_leidas": "Filas leídas del archivo.",
    "filas_cargadas": "Filas insertadas en la base.",
    "filas_rechazadas": "Filas rechazadas por validación.",
    "duplicados": "Registros duplicados (archivo + base).",
    "detalle": "Resumen JSON del proceso (pasos, nulos, muestra de errores).",
}


def main() -> None:
    engine = create_engine("sqlite://")
    ddl = ["-- Esquema generado automáticamente desde src/database/models.py", "-- Montos en COP como enteros (BIGINT).",
           "PRAGMA foreign_keys = ON;", ""]
    for table in Base.metadata.sorted_tables:
        ddl.append(str(CreateTable(table).compile(engine)).strip() + ";")
        for idx in sorted(table.indexes, key=lambda i: i.name):
            ddl.append(str(CreateIndex(idx).compile(engine)).strip() + ";")
        ddl.append("")
    (ROOT / "sql" / "schema.sql").write_text("\n".join(ddl), encoding="utf-8")

    md = ["# Diccionario de datos", "",
          "> Generado automáticamente con `python scripts/generate_schema_docs.py` a partir de "
          "`src/database/models.py`. Todos los importes están en **pesos colombianos (COP) como enteros**.", ""]
    for table in Base.metadata.sorted_tables:
        md += [f"## `{table.name}`", "", TABLE_DESC.get(table.name, ""), "",
               "| Columna | Tipo | Nulo | Llave | Descripción |", "|---|---|---|---|---|"]
        for col in table.columns:
            key = "PK" if col.primary_key else ""
            if col.foreign_keys:
                fk = next(iter(col.foreign_keys))
                key = (key + " " if key else "") + f"FK → {fk.target_fullname}"
            if any(isinstance(c, UniqueConstraint) and col.name in c.columns for c in table.constraints) or col.unique:
                key = (key + " " if key else "") + "Único"
            md.append(f"| `{col.name}` | {col.type} | {'Sí' if col.nullable else 'No'} | {key} | "
                      f"{COL_DESC.get(col.name, '')} |")
        checks = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        if checks:
            md += ["", "Restricciones: " + "; ".join(f"`{c.sqltext}`" for c in checks)]
        idx = [f"`{i.name}` ({', '.join(c.name for c in i.columns)})" for i in table.indexes]
        if idx:
            md += ["", "Índices: " + ", ".join(sorted(idx))]
        md.append("")
    (ROOT / "docs" / "diccionario_datos.md").write_text("\n".join(md), encoding="utf-8")
    print("Generados sql/schema.sql y docs/diccionario_datos.md")


if __name__ == "__main__":
    main()
