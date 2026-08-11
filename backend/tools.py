"""
tools.py
--------
Aquí viven las "herramientas" (funciones) reales que el modelo de OpenAI
puede invocar mediante Function Calling. Cada función:
  1. Hace un trabajo concreto y determinístico (consultar inventario,
     consultar proveedores, agrupar por sección).
  2. Devuelve un dict serializable a JSON (lo que el modelo recibe de vuelta).

El LLM nunca inventa datos de stock ni de precios: siempre pasa por estas
funciones. Esto reduce alucinaciones y hace el sistema auditable.
"""
from typing import Dict, List
from storage import cargar_inventario, cargar_proveedores

SECCIONES_VALIDAS = ["Cuarto", "Cocina", "Baño", "Sala/Recepción"]


def verificar_inventario(seccion: str) -> Dict:
    """
    Revisa el inventario de una sección específica y devuelve solo
    los ítems cuyo stock actual está por debajo (o igual) del mínimo requerido.
    """
    inventario = cargar_inventario()
    if seccion not in inventario:
        return {"error": f"Sección '{seccion}' no reconocida.", "secciones_validas": SECCIONES_VALIDAS}

    items_bajos = []
    for item in inventario[seccion]:
        if item["stock_actual"] <= item["stock_minimo"]:
            items_bajos.append(item)

    return {
        "seccion": seccion,
        "items_bajo_minimo": items_bajos,
        "total_items_criticos": len(items_bajos),
    }


def cotizar_proveedores(item: str, cantidad: int) -> Dict:
    """
    Busca los proveedores disponibles para un ítem y calcula el costo total
    con cada uno, devolviendo también cuál conviene (precio) y cuál es más rápido.
    """
    proveedores = cargar_proveedores()
    opciones = proveedores.get(item)

    if not opciones:
        return {"error": f"No hay proveedores registrados para '{item}'."}

    cotizaciones = []
    for op in opciones:
        cotizaciones.append({
            "proveedor": op["proveedor"],
            "precio_unitario": op["precio_unitario"],
            "tiempo_entrega_dias": op["tiempo_entrega_dias"],
            "subtotal": round(op["precio_unitario"] * cantidad, 2),
        })

    mas_barato = min(cotizaciones, key=lambda c: c["subtotal"])
    mas_rapido = min(cotizaciones, key=lambda c: c["tiempo_entrega_dias"])

    return {
        "item": item,
        "cantidad": cantidad,
        "cotizaciones": cotizaciones,
        "recomendado_por_precio": mas_barato,
        "recomendado_por_velocidad": mas_rapido,
    }


def agrupar_por_seccion(items_con_seccion: List[Dict]) -> Dict:
    """
    Recibe una lista de ítems ya evaluados (cada uno con su 'seccion')
    y los agrupa. Útil para que el agente confirme la estructura final
    antes de generar la propuesta de pedido por sección.
    """
    agrupado: Dict[str, List[Dict]] = {s: [] for s in SECCIONES_VALIDAS}
    for it in items_con_seccion:
        seccion = it.get("seccion")
        if seccion in agrupado:
            agrupado[seccion].append(it)
    return {"agrupado_por_seccion": agrupado}


# ---------------------------------------------------------------------------
# Definición de las tools en formato OpenAI (JSON Schema) para Function Calling
# ---------------------------------------------------------------------------
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "verificar_inventario",
            "description": (
                "Consulta el inventario real de una sección del hostal "
                "(Cuarto, Cocina, Baño o Sala/Recepción) y devuelve únicamente "
                "los ítems cuyo stock está en o por debajo del mínimo permitido."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seccion": {
                        "type": "string",
                        "enum": SECCIONES_VALIDAS,
                        "description": "Sección exacta a inspeccionar.",
                    }
                },
                "required": ["seccion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cotizar_proveedores",
            "description": (
                "Consulta precios reales de proveedores para un ítem específico "
                "y calcula el costo total según la cantidad solicitada. "
                "Devuelve la opción más barata y la más rápida."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "Nombre exacto del ítem a cotizar."},
                    "cantidad": {"type": "integer", "description": "Cantidad a comprar."},
                },
                "required": ["item", "cantidad"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agrupar_por_seccion",
            "description": (
                "Agrupa una lista de ítems ya cotizados por su sección "
                "(Cuarto, Cocina, Baño, Sala/Recepción) para construir la "
                "estructura final de las propuestas de pedido."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items_con_seccion": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "description": "Ítem evaluado, debe incluir la clave 'seccion'.",
                        },
                    }
                },
                "required": ["items_con_seccion"],
            },
        },
    },
]

# Mapa nombre -> función real, usado por el orquestador para ejecutar la tool call
TOOL_IMPLEMENTATIONS = {
    "verificar_inventario": verificar_inventario,
    "cotizar_proveedores": cotizar_proveedores,
    "agrupar_por_seccion": agrupar_por_seccion,
}
