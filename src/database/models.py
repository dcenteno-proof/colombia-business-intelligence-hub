"""Modelo relacional (SQLAlchemy 2.0, declarativo).

Decisión de diseño sobre importes: los valores monetarios se almacenan como
ENTEROS en pesos colombianos (COP). El peso no usa centavos en la operación
comercial, y almacenar enteros elimina por completo los errores de redondeo
de punto flotante en sumas y restas. Los ratios (márgenes, crecimientos) se
calculan en la capa analítica y sólo ahí se convierten a decimal.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Moneda: BIGINT en COP (en SQLite se almacena como INTEGER de 64 bits).
Money = BigInteger


class Base(DeclarativeBase):
    pass


class Region(Base):
    __tablename__ = "regiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    ciudad_principal: Mapped[str] = mapped_column(String(60), nullable=False)

    vendedores: Mapped[list["Vendedor"]] = relationship(back_populates="region")
    clientes: Mapped[list["Cliente"]] = relationship(back_populates="region")


class Vendedor(Base):
    __tablename__ = "vendedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    region_id: Mapped[int] = mapped_column(ForeignKey("regiones.id", ondelete="RESTRICT"), nullable=False, index=True)
    fecha_ingreso: Mapped[date] = mapped_column(Date, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    origen: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")

    region: Mapped[Region] = relationship(back_populates="vendedores")


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(200))

    productos: Mapped[list["Producto"]] = relationship(back_populates="categoria")


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(60), nullable=False)
    plazo_pago_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    lead_time_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    origen: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")

    __table_args__ = (
        CheckConstraint("plazo_pago_dias >= 0", name="ck_proveedor_plazo"),
        CheckConstraint("lead_time_dias >= 0", name="ck_proveedor_lead_time"),
    )


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False, index=True)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id", ondelete="SET NULL"), index=True)
    unidad: Mapped[str] = mapped_column(String(20), nullable=False, default="UND")
    precio_lista: Mapped[int] = mapped_column(Money, nullable=False)
    costo_unitario: Mapped[int] = mapped_column(Money, nullable=False)
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    origen: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")

    categoria: Mapped[Categoria] = relationship(back_populates="productos")

    __table_args__ = (
        CheckConstraint("precio_lista >= 0", name="ck_producto_precio"),
        CheckConstraint("costo_unitario >= 0", name="ck_producto_costo"),
        CheckConstraint("stock_minimo >= 0", name="ck_producto_stock_min"),
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    region_id: Mapped[int] = mapped_column(ForeignKey("regiones.id", ondelete="RESTRICT"), nullable=False, index=True)
    ciudad: Mapped[str] = mapped_column(String(60), nullable=False)
    fecha_registro: Mapped[date] = mapped_column(Date, nullable=False)
    origen: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")

    region: Mapped[Region] = relationship(back_populates="clientes")


class Venta(Base):
    """Encabezado de factura de venta."""

    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_factura: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False)
    vendedor_id: Mapped[int | None] = mapped_column(ForeignKey("vendedores.id", ondelete="SET NULL"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regiones.id", ondelete="RESTRICT"), nullable=False)
    canal: Mapped[str] = mapped_column(String(30), nullable=False, default="Preventa")
    origen: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")

    detalles: Mapped[list["DetalleVenta"]] = relationship(back_populates="venta", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_ventas_fecha", "fecha"),
        Index("ix_ventas_cliente_fecha", "cliente_id", "fecha"),
        Index("ix_ventas_region", "region_id"),
        Index("ix_ventas_vendedor", "vendedor_id"),
    )


class DetalleVenta(Base):
    """Línea de factura. ``costo_unitario`` es una foto del costo vigente en la fecha de venta."""

    __tablename__ = "detalle_ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False, index=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[int] = mapped_column(Money, nullable=False)
    descuento: Mapped[int] = mapped_column(Money, nullable=False, default=0)
    cantidad_devuelta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    costo_unitario: Mapped[int] = mapped_column(Money, nullable=False)

    venta: Mapped[Venta] = relationship(back_populates="detalles")

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_dv_cantidad"),
        CheckConstraint("precio_unitario >= 0", name="ck_dv_precio"),
        CheckConstraint("descuento >= 0", name="ck_dv_descuento"),
        CheckConstraint("descuento <= cantidad * precio_unitario", name="ck_dv_descuento_max"),
        CheckConstraint("cantidad_devuelta >= 0 AND cantidad_devuelta <= cantidad", name="ck_dv_devolucion"),
        CheckConstraint("costo_unitario >= 0", name="ck_dv_costo"),
    )


class Compra(Base):
    """Orden de compra a proveedor."""

    __tablename__ = "compras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_orden: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False, index=True)
    fecha_orden: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_esperada: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_recepcion: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="RECIBIDA")
    origen: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")

    detalles: Mapped[list["DetalleCompra"]] = relationship(back_populates="compra", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_compras_fecha", "fecha_orden"),
        CheckConstraint("fecha_esperada >= fecha_orden", name="ck_compra_fechas"),
        CheckConstraint("estado IN ('PENDIENTE','RECIBIDA','PARCIAL','CANCELADA')", name="ck_compra_estado"),
    )


class DetalleCompra(Base):
    __tablename__ = "detalle_compras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    compra_id: Mapped[int] = mapped_column(ForeignKey("compras.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False, index=True)
    cantidad_pedida: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_recibida: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    costo_unitario: Mapped[int] = mapped_column(Money, nullable=False)

    compra: Mapped[Compra] = relationship(back_populates="detalles")

    __table_args__ = (
        CheckConstraint("cantidad_pedida > 0", name="ck_dc_pedida"),
        CheckConstraint("cantidad_recibida >= 0", name="ck_dc_recibida"),
        CheckConstraint("costo_unitario >= 0", name="ck_dc_costo"),
    )


class Inventario(Base):
    """Foto (snapshot) del inventario al cierre de cada mes, por producto."""

    __tablename__ = "inventario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    fecha_corte: Mapped[date] = mapped_column(Date, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[int] = mapped_column(Money, nullable=False)
    valor: Mapped[int] = mapped_column(Money, nullable=False)

    __table_args__ = (
        UniqueConstraint("producto_id", "fecha_corte", name="uq_inventario_producto_corte"),
        Index("ix_inventario_corte", "fecha_corte"),
        CheckConstraint("cantidad >= 0", name="ck_inv_cantidad"),
        CheckConstraint("valor >= 0", name="ck_inv_valor"),
    )


class MovimientoInventario(Base):
    """Kardex. ``cantidad`` con signo: positiva = entrada, negativa = salida."""

    __tablename__ = "movimientos_inventario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[int] = mapped_column(Money, nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        Index("ix_mov_producto_fecha", "producto_id", "fecha"),
        CheckConstraint("cantidad <> 0", name="ck_mov_cantidad"),
        CheckConstraint(
            "tipo IN ('INVENTARIO_INICIAL','ENTRADA_COMPRA','SALIDA_VENTA','DEVOLUCION_CLIENTE','AJUSTE')",
            name="ck_mov_tipo",
        ),
    )


class GastoOperativo(Base):
    __tablename__ = "gastos_operativos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    categoria_gasto: Mapped[str] = mapped_column(String(60), nullable=False)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regiones.id", ondelete="SET NULL"))
    descripcion: Mapped[str | None] = mapped_column(String(200))
    monto: Mapped[int] = mapped_column(Money, nullable=False)
    origen: Mapped[str] = mapped_column(String(80), nullable=False, default="DEMO")

    __table_args__ = (
        Index("ix_gastos_fecha", "fecha"),
        CheckConstraint("monto > 0", name="ck_gasto_monto"),
    )


class Costo(Base):
    """Historial de costo unitario por producto (vigente desde ``fecha_vigencia``)."""

    __tablename__ = "costos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="CASCADE"), nullable=False)
    fecha_vigencia: Mapped[date] = mapped_column(Date, nullable=False)
    costo_unitario: Mapped[int] = mapped_column(Money, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        UniqueConstraint("producto_id", "fecha_vigencia", name="uq_costo_producto_fecha"),
        CheckConstraint("costo_unitario >= 0", name="ck_costo_valor"),
    )


class RegistroImportacion(Base):
    """Bitácora del proceso ETL: un registro por archivo procesado."""

    __tablename__ = "registro_importaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Hora local del equipo (CURRENT_TIMESTAMP de SQLite sería UTC).
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now().replace(microsecond=0))
    archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    entidad: Mapped[str] = mapped_column(String(40), nullable=False)
    filas_leidas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filas_cargadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filas_rechazadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    detalle: Mapped[str | None] = mapped_column(Text)


ALL_TABLES = [t.name for t in Base.metadata.sorted_tables]
