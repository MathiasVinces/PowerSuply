"""
agent.py
--------
Orquestador del "Agente de Compras" de SmartSupply usando la API de OpenAI
(Chat Completions + Function Calling).

Flujo por sección (Cuarto, Cocina, Baño, Sala/Recepción):
  1. El modelo llama a `verificar_inventario` para ver qué está bajo de stock.
  2. Por cada ítem crítico, el modelo llama a `cotizar_proveedores` para
     obtener precios reales y decidir cantidad + proveedor.
  3. El modelo devuelve una propuesta ESTRUCTURADA (JSON) con su razonamiento
     por cada ítem (justificacion).
  4. El backend guarda la propuesta como una OrdenPedido en estado "pendiente"
     y registra toda la traza (qué tool llamó, con qué argumentos, qué
     respondió) en el log de trazabilidad.
  5. El agente NUNCA ejecuta la compra: solo dejará la orden lista para que
     un humano la apruebe o rechace desde el frontend (ver main.py).

Nota sobre "OpenAI Agents SDK": este archivo usa la API estándar de
Function Calling porque es la forma más portable/estable para un MVP de
hackathon. La migración al Agents SDK (`from agents import Agent, Runner`)
es directa: cada función de tools.py se envuelve con el decorador
`@function_tool` y este mismo bucle lo reemplaza `Runner.run(agent, input)`.
Se documenta la equivalencia en el README.
"""
import json
import os
from openai import OpenAI
from typing import List, Dict
from models import OrdenPedido, ItemPedido, LogEntry
from storage import agregar_orden, registrar_log
from tools import TOOLS_SCHEMA, TOOL_IMPLEMENTATIONS, SECCIONES_VALIDAS

# 1. Agrega estas dos líneas para que Python lea tu archivo .env
from dotenv import load_dotenv
load_dotenv() 

# 2. Ahora sí, os.getenv encontrará las variables sin problema
MODEL = "llama-3.3-70b-versatile"
client = OpenAI(
    api_key="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",
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """Eres el Agente de Compras de SmartSupply, un asistente para
un hostal/pyme. Tu trabajo es analizar UNA sección a la vez (Cuarto, Cocina,
Baño o Sala/Recepción), detectar qué insumos están en o bajo el stock mínimo,
cotizar proveedores reales usando las herramientas disponibles, y proponer
una orden de compra clara y justificada.

Reglas estrictas:
- SIEMPRE usa la herramienta `verificar_inventario` primero para esa sección.
- Para cada ítem crítico detectado, usa `cotizar_proveedores` antes de
  decidir cantidad y proveedor. Nunca inventes precios ni stock.
- La cantidad a pedir debe llevar la sección de vuelta a un nivel seguro
  (usualmente el stock_minimo más un pequeño colchón del 20%, redondeado
  hacia arriba), nunca una cifra arbitraria.
- Prioriza el proveedor más barato salvo que el tiempo de entrega sea crítico
  (más de 4 días de diferencia); si eliges otro proveedor, explica por qué.
- NO tienes permitido ejecutar ni confirmar la compra. Solo preparas la
  propuesta para revisión humana.
- Al final, responde EXCLUSIVAMENTE con un JSON (sin texto adicional, sin
  markdown) con esta forma exacta:
{
  "seccion": "<Cuarto|Cocina|Baño|Sala/Recepción>",
  "razonamiento_general": "<resumen breve de tu análisis general>",
  "items": [
    {
      "item": "<nombre>",
      "cantidad_a_pedir": <int>,
      "stock_actual": <int>,
      "stock_minimo": <int>,
      "proveedor_elegido": "<nombre proveedor>",
      "precio_unitario": <float>,
      "subtotal": <float>,
      "justificacion": "<por qué esa cantidad y ese proveedor, en 1-2 frases>"
    }
  ]
}
Si no hay ítems críticos en la sección, responde con "items": [] y explica
en razonamiento_general que la sección está saludable.
"""


def _ejecutar_tool_call(tool_call, orden_id_temporal: str) -> str:
    """Ejecuta la función real solicitada por el modelo y deja traza de la acción."""
    nombre = tool_call.function.name
    args = json.loads(tool_call.function.arguments or "{}")

    fn = TOOL_IMPLEMENTATIONS.get(nombre)
    if fn is None:
        resultado = {"error": f"Tool '{nombre}' no implementada."}
    else:
        resultado = fn(**args)

    registrar_log(LogEntry(
        actor="agente",
        accion=f"tool_call:{nombre}",
        detalle=f"args={args} -> resultado={json.dumps(resultado, ensure_ascii=False)[:500]}",
        orden_id=orden_id_temporal,
    ))
    return json.dumps(resultado, ensure_ascii=False)


def analizar_seccion(seccion: str, max_turns: int = 6) -> Dict:
    """Corre el bucle de Function Calling para UNA sección y devuelve la propuesta cruda."""
    if seccion not in SECCIONES_VALIDAS:
        raise ValueError(f"Sección inválida: {seccion}")

    messages: List[Dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Analiza la sección '{seccion}' y prepara la propuesta de pedido."},
    ]

    registrar_log(LogEntry(actor="agente", accion="inicio_analisis", detalle=f"Sección: {seccion}"))

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = response.choices[0].message
        print("\n" + "="*40)
        print(f"HERRAMIENTAS USADAS: {msg.tool_calls}")
        print(f"TEXTO DE LA IA: {msg.content}")
        print("="*40 + "\n")
        messages.append(msg.model_dump(exclude_none=True))

        if msg.tool_calls:
            for tc in msg.tool_calls:
                resultado_json = _ejecutar_tool_call(tc, orden_id_temporal=seccion)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": resultado_json,
                })
            continue  # el modelo sigue razonando con los resultados de las tools

        # No hay más tool calls: esta es la respuesta final (debe ser JSON puro)
        contenido = msg.content.strip()
        contenido = contenido.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            propuesta = json.loads(contenido)
        except json.JSONDecodeError:
            registrar_log(LogEntry(
                actor="sistema", accion="error_parseo",
                detalle=f"Respuesta no era JSON válido: {contenido[:300]}",
            ))
            raise
        return propuesta

    raise RuntimeError(f"El agente no concluyó el análisis de '{seccion}' en {max_turns} turnos.")


def generar_propuesta_y_guardar(seccion: str) -> OrdenPedido | None:
    """Analiza la sección, y si hay ítems críticos, crea y persiste una OrdenPedido pendiente."""
    propuesta = analizar_seccion(seccion)

    if not propuesta.get("items"):
        registrar_log(LogEntry(
            actor="agente", accion="seccion_saludable",
            detalle=propuesta.get("razonamiento_general", "Sin ítems críticos."),
        ))
        return None

    items = [ItemPedido(**it) for it in propuesta["items"]]
    total = round(sum(it.subtotal for it in items), 2)

    orden = OrdenPedido(
        seccion=seccion,
        items=items,
        total_estimado=total,
        razonamiento_general=propuesta.get("razonamiento_general", ""),
    )
    agregar_orden(orden)

    registrar_log(LogEntry(
        actor="agente", accion="propuesta_generada",
        detalle=f"{len(items)} ítem(s), total estimado ${total}. Razonamiento: {orden.razonamiento_general}",
        orden_id=orden.id,
    ))
    return orden


def ejecutar_agente_para_todas_las_secciones() -> List[OrdenPedido]:
    """Corre el agente sección por sección (Cuarto, Cocina, Baño, Sala/Recepción)."""
    ordenes_creadas = []
    for seccion in SECCIONES_VALIDAS:
        try:
            orden = generar_propuesta_y_guardar(seccion)
            if orden:
                ordenes_creadas.append(orden)
        except Exception as e:
            registrar_log(LogEntry(
                actor="sistema", accion="error_seccion",
                detalle=f"Fallo analizando '{seccion}': {str(e)}",
            ))
    return ordenes_creadas
