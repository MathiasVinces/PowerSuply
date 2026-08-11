"""
Modelos de datos (Pydantic) usados en toda la aplicación SmartSupply.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
import uuid

SeccionType = Literal["Cuarto", "Cocina", "Baño", "Sala/Recepción"]
EstadoOrden = Literal["pendiente", "aprobada", "rechazada"]


class ItemPedido(BaseModel):
    item: str
    cantidad_a_pedir: int
    stock_actual: int
    stock_minimo: int
    proveedor_elegido: str
    precio_unitario: float
    subtotal: float
    justificacion: str  # razonamiento del agente: por qué esa cantidad / proveedor


class OrdenPedido(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    seccion: SeccionType
    items: List[ItemPedido]
    total_estimado: float
    estado: EstadoOrden = "pendiente"
    creado_en: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    resuelto_en: Optional[str] = None
    resuelto_por: Optional[str] = None
    razonamiento_general: str = ""


class LogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    actor: str  # "agente" | "humano" | "sistema"
    accion: str
    detalle: str
    orden_id: Optional[str] = None


class AprobacionRequest(BaseModel):
    admin: str = "Administrador"
    comentario: Optional[str] = None
