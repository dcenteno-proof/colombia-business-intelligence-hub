"""Crea archivos de ejemplo (DEMO) para probar el ETL desde el Centro de datos.

Cada archivo incluye, a propósito, registros válidos y registros con problemas
típicos de calidad (fechas inválidas, nulos, duplicados, categorías mal
escritas, referencias inexistentes, importes en formato colombiano).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import SAMPLE_DIR


def sales_sample() -> pd.DataFrame:
    rows = [
        # numero_factura, fecha, cliente, vendedor, sku, cantidad, precio, descuento, devuelta, canal
        ("IMP-FV-0001", "03/10/2026", "DEMO-CLI-010", "DEMO-VEN-01", "DEMO-01001", "24", "2.400", "0", "0", "Preventa"),
        ("IMP-FV-0001", "03/10/2026", "DEMO-CLI-010", "DEMO-VEN-01", "DEMO-01003", "12", "4.550", "1.000", "0", "Preventa"),
        ("IMP-FV-0002", "2026-10-05", "DEMO-CLI-022", "DEMO-VEN-03", "DEMO-02013", "48", "$ 5.000", "", "2", "Televenta"),
        ("IMP-FV-0002", "2026-10-05", "DEMO-CLI-022", "DEMO-VEN-03", "DEMO-02014", "60", "1400", "0", "0", "Televenta"),
        ("IMP-FV-0003", "07/10/2026", "DEMO-CLI-035", "", "DEMO-03019", "10", "11.300", "500", "0", "Preventa"),
        ("IMP-FV-0003", "07/10/2026", "DEMO-CLI-035", "", "DEMO-03019", "10", "11.300", "500", "0", "Preventa"),  # duplicado
        ("IMP-FV-0004", "31/02/2026", "DEMO-CLI-040", "DEMO-VEN-05", "DEMO-01002", "5", "22.000", "0", "0", "Preventa"),  # fecha inválida
        ("IMP-FV-0005", "08/10/2026", "DEMO-CLI-999", "DEMO-VEN-02", "DEMO-01001", "10", "2.400", "0", "0", "Preventa"),  # cliente no existe
        ("IMP-FV-0006", "09/10/2026", "DEMO-CLI-050", "DEMO-VEN-04", "DEMO-01004", "-3", "9.900", "0", "0", "Preventa"),  # cantidad negativa
        ("IMP-FV-0007", "10/10/2026", "DEMO-CLI-055", "DEMO-VEN-06", "", "6", "3.100", "0", "0", "Preventa"),  # sku vacío
        ("IMP-FV-0008", "11/10/2026", "DEMO-CLI-060", "DEMO-VEN-07", "DEMO-04027", "4", "15.000", "90.000", "0", "Preventa"),  # descuento > bruto
        ("IMP-FV-0009", "12/10/2026", "DEMO-CLI-061", "DEMO-VEN-08", "DEMO-06039", "20", "4.500", "0", "25", "Preventa"),  # devuelve más
        ("IMP-FV-0010", "13/10/2026", "DEMO-CLI-070", "DEMO-VEN-09", "DEMO-05033", "36", "5.400", "2.000", "0", "Comercio electrónico B2B"),
        ("IMP-FV-0010", "13/10/2026", "DEMO-CLI-070", "DEMO-VEN-09", "DEMO-05035", "40", "1.950", "0", "0", "Comercio electrónico B2B"),
        ("IMP-FV-0011", "14/10/2026", "DEMO-CLI-080", "DEMO-VEN-10", "DEMO-07045", "1,5", "6.200", "0", "0", "Preventa"),  # cantidad decimal
        ("", "", "", "", "", "", "", "", "", ""),  # fila vacía
    ]
    cols = ["Numero Factura", "Fecha", "Codigo Cliente", "Codigo Vendedor", "SKU", "Cantidad", "Precio Unitario",
            "Descuento", "Cantidad Devuelta", "Canal"]
    return pd.DataFrame(rows, columns=cols)


def customers_sample() -> pd.DataFrame:
    rows = [
        ("IMP-CLI-001", "Tienda Nueva Aurora DEMO-IMP1", "tienda de barrio", "andina ", "Bogotá", "2026-09-01"),
        ("IMP-CLI-002", "Minimercado El Faro DEMO-IMP2", "MINIMERCADO", "Caribe", "Cartagena", "15/09/2026"),
        ("IMP-CLI-003", "Restaurante Sabor DEMO-IMP3", "horeca", "Pacifico", "Cali", "2026-09-20"),
        ("IMP-CLI-004", "  Supermercado   La Loma DEMO-IMP4 ", "Supermercado independiente", "ANTIOQUIA", "Medellín", ""),
        ("IMP-CLI-005", "Casino Planta Norte DEMO-IMP5", "Institucional", "Amazonía", "Leticia", "2026-09-25"),  # región inexistente
        ("IMP-CLI-002", "Minimercado El Faro DEMO-IMP2", "Minimercado", "Caribe", "Cartagena", "15/09/2026"),  # duplicado
        ("IMP-CLI-006", "", "Tienda de barrio", "Santanderes", "Cúcuta", "2026-10-01"),  # nombre vacío
        ("DEMO-CLI-010", "Cliente ya existente DEMO", "Tienda de barrio", "Andina", "Bogotá", "2026-10-01"),  # ya existe
    ]
    return pd.DataFrame(rows, columns=["Código", "Nombre", "Tipo Cliente", "Región", "Ciudad", "Fecha Registro"])


def products_sample() -> pd.DataFrame:
    rows = [
        ("IMP-SKU-001", "Agua con gas 600 ml", "bebidas ", "UND", "1.900", "1.400", "50", "DEMO-PRV-02"),
        ("IMP-SKU-002", "Esponja multiuso x3", "ASEO DEL HOGAR", "PAQ", "4.200", "3.000", "30", "DEMO-PRV-03"),
        ("IMP-SKU-003", "Alimento para gato 1 kg", "mascotas", "UND", "18.900", "14.200", "20", ""),  # categoría nueva
        ("IMP-SKU-004", "Galletas de soda x9", "Snacks y confiteria", "PAQ", "5.600", "-4.100", "25", "DEMO-PRV-05"),  # costo negativo
        ("IMP-SKU-005", "Servilletas cocteleras x100", "Desechables", "PAQ", "3.300", "2.400", "", "DEMO-PRV-99"),  # proveedor no existe
        ("IMP-SKU-001", "Agua con gas 600 ml", "Bebidas", "UND", "1.900", "1.400", "50", "DEMO-PRV-02"),  # duplicado
    ]
    return pd.DataFrame(rows, columns=["SKU", "Nombre Producto", "Categoría", "Unidad", "Precio Lista",
                                       "Costo Unitario", "Stock Minimo", "Proveedor"])


def expenses_sample() -> pd.DataFrame:
    rows = [
        ("2026-10-15", "Mantenimiento de vehículos", "Andina", "Mantenimiento flota (DEMO)", "3.250.000"),
        ("2026-10-16", "transporte y logística", "Caribe", "Fletes adicionales (DEMO)", "1.800.000"),
        ("2026-10-18", "Capacitación", "Corporativo", "Capacitación comercial (DEMO)", "2.100.000"),
        ("2026-10-20", "Servicios públicos", "Andina", "Energía bodega (DEMO)", "0"),  # monto cero
        ("2026-13-01", "Gastos administrativos", "", "Papelería (DEMO)", "450.000"),  # fecha inválida
    ]
    return pd.DataFrame(rows, columns=["Fecha", "Categoría Gasto", "Región", "Descripción", "Monto"])


def write_samples(target: Path | str = SAMPLE_DIR) -> list[Path]:
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    paths = [target / "ventas_ejemplo.csv", target / "clientes_ejemplo.xlsx", target / "productos_ejemplo.csv",
             target / "gastos_ejemplo.xlsx"]
    sales_sample().to_csv(paths[0], index=False, sep=";", encoding="utf-8-sig")
    customers_sample().to_excel(paths[1], index=False, sheet_name="clientes")
    products_sample().to_csv(paths[2], index=False, encoding="utf-8-sig")
    expenses_sample().to_excel(paths[3], index=False, sheet_name="gastos")
    return paths
