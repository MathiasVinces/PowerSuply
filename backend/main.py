"""
main.py
-------
API FastAPI de SmartSupply. Expone:

  GET  /api/dashboard          -> estado agregado por sección (para las 4 tarjetas)
  POST /api/agente/ejecutar    -> dispara el agente (analiza las 4 secciones y
                                   crea órdenes pendientes, sin ejecutarlas)
  GET  /api/ordenes            -> lista de órdenes (todas o filtradas por estado)
  POST /api/ordenes/{id}/aprobar
  POST /api/ordenes/{id}/rechazar
  GET  /api/logs               -> trazabilidad completa del agente
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional
##CAMBIE EL API
##SE CAMBIA
##BLOQUEADO
from models import AprobacionRequest, LogEntry
from storage import cargar_inventario, cargar_ordenes, actualizar_orden, registrar_log, cargar_logs
from agent import ejecutar_agente_para_todas_las_secciones
from tools import SECCIONES_VALIDAS

app = FastAPI(title="SmartSupply API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción: restringir al dominio del frontend
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/dashboard")
def dashboard():
    """Devuelve, por cada sección, el total de ítems, cuántos están críticos y el % de salud."""
    inventario = cargar_inventario()
    ordenes = cargar_ordenes()
    resumen = {}
    for seccion in SECCIONES_VALIDAS:
        items = inventario.get(seccion, [])
        criticos = [i for i in items if i["stock_actual"] <= i["stock_minimo"]]
        salud = round(100 * (1 - len(criticos) / len(items)), 1) if items else 100.0
        ordenes_pendientes_seccion = [o for o in ordenes if o["seccion"] == seccion and o["estado"] == "pendiente"]
        resumen[seccion] = {
            "total_items": len(items),
            "items_criticos": len(criticos),
            "salud_pct": salud,
            "ordenes_pendientes": len(ordenes_pendientes_seccion),
            "items": items,
        }
    return resumen


@app.post("/api/agente/ejecutar")
def ejecutar_agente():
    """Dispara al agente de OpenAI para analizar las 4 secciones y generar propuestas."""
    registrar_log(LogEntry(actor="sistema", accion="ejecucion_manual", detalle="Disparado desde el frontend."))
    ordenes = ejecutar_agente_para_todas_las_secciones()
    return {
        "mensaje": f"Análisis completo. {len(ordenes)} propuesta(s) de pedido generada(s).",
        "ordenes_generadas": [o.id for o in ordenes],
    }


@app.get("/api/ordenes")
def listar_ordenes(estado: Optional[str] = None):
    ordenes = cargar_ordenes()
    if estado:
        ordenes = [o for o in ordenes if o["estado"] == estado]
    ordenes.sort(key=lambda o: o["creado_en"], reverse=True)
    return ordenes


@app.post("/api/ordenes/{orden_id}/aprobar")
def aprobar_orden(orden_id: str, body: AprobacionRequest):
    orden = actualizar_orden(orden_id, {
        "estado": "aprobada",
        "resuelto_en": datetime.utcnow().isoformat(),
        "resuelto_por": body.admin,
    })
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    registrar_log(LogEntry(
        actor="humano", accion="orden_aprobada",
        detalle=f"Aprobada por {body.admin}. Comentario: {body.comentario or '—'}",
        orden_id=orden_id,
    ))
    return orden


@app.post("/api/ordenes/{orden_id}/rechazar")
def rechazar_orden(orden_id: str, body: AprobacionRequest):
    orden = actualizar_orden(orden_id, {
        "estado": "rechazada",
        "resuelto_en": datetime.utcnow().isoformat(),
        "resuelto_por": body.admin,
    })
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    registrar_log(LogEntry(
        actor="humano", accion="orden_rechazada",
        detalle=f"Rechazada por {body.admin}. Comentario: {body.comentario or '—'}",
        orden_id=orden_id,
    ))
    return orden


@app.get("/api/logs")
def logs():
    registros = cargar_logs()
    registros.sort(key=lambda r: r["timestamp"], reverse=True)
    return registros


@app.get("/api/health")
def health():
    return {"status": "ok"}
