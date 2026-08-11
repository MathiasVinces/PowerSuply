"""
Capa de persistencia ligera para el MVP.
Usa archivos JSON en disco para no depender de una base de datos
(suficiente para un hackathon; migrar a Postgres/SQLite es directo después).
"""
import json
import os
from typing import Dict, List
from threading import Lock
from models import OrdenPedido, LogEntry

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
INVENTARIO_PATH = os.path.join(DATA_DIR, "inventario.json")
PROVEEDORES_PATH = os.path.join(DATA_DIR, "proveedores.json")
ORDENES_PATH = os.path.join(DATA_DIR, "ordenes.json")
LOG_PATH = os.path.join(LOGS_DIR, "trazabilidad.log")
LOG_JSON_PATH = os.path.join(LOGS_DIR, "trazabilidad.json")

_lock = Lock()

os.makedirs(LOGS_DIR, exist_ok=True)
if not os.path.exists(ORDENES_PATH):
    with open(ORDENES_PATH, "w", encoding="utf-8") as f:
        json.dump([], f)
if not os.path.exists(LOG_JSON_PATH):
    with open(LOG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump([], f)


def cargar_inventario() -> Dict:
    with open(INVENTARIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_proveedores() -> Dict:
    with open(PROVEEDORES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_ordenes() -> List[dict]:
    with open(ORDENES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_ordenes(ordenes: List[dict]) -> None:
    with _lock:
        with open(ORDENES_PATH, "w", encoding="utf-8") as f:
            json.dump(ordenes, f, ensure_ascii=False, indent=2)


def agregar_orden(orden: OrdenPedido) -> None:
    ordenes = cargar_ordenes()
    ordenes.append(json.loads(orden.model_dump_json()))
    guardar_ordenes(ordenes)


def actualizar_orden(orden_id: str, cambios: dict) -> dict | None:
    ordenes = cargar_ordenes()
    actualizada = None
    for o in ordenes:
        if o["id"] == orden_id:
            o.update(cambios)
            actualizada = o
            break
    guardar_ordenes(ordenes)
    return actualizada


def registrar_log(entry: LogEntry) -> None:
    """Escribe la traza tanto en texto plano (legible) como en JSON (consultable por la API)."""
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            linea = f"[{entry.timestamp}] ({entry.actor.upper()}) {entry.accion}"
            if entry.orden_id:
                linea += f" | orden={entry.orden_id}"
            linea += f" -> {entry.detalle}\n"
            f.write(linea)

        with open(LOG_JSON_PATH, "r", encoding="utf-8") as f:
            logs = json.load(f)
        logs.append(json.loads(entry.model_dump_json()))
        with open(LOG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)


def cargar_logs() -> List[dict]:
    with open(LOG_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
