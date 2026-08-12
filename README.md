# 📦 SmartSupply — Agente de Compras para Pymes

> **Temática del hackathon:** Agentes y automatización con propósito
> **ODS Alineados:** 8 (Trabajo decente y crecimiento económico) · 9 (Industria, innovación e infraestructura)

**SmartSupply** es un MVP de sistema **multiagente con supervisión humana** que automatiza el abastecimiento de suministros en hostales y pequeñas empresas.

El agente revisa el inventario por sección (**Cuarto, Cocina, Baño, Sala/Recepción**), detecta lo que está por debajo del stock mínimo, cotiza proveedores y arma una propuesta de pedido estructurada y justificada. Sin embargo, **nunca ejecuta la compra por sí solo**: la deja lista en una bandeja para que un administrador humano apruebe o rechace con un clic.

---

## 🏗️ Arquitectura del Proyecto

```text
smartsupply/
├── backend/
│   ├── main.py              # API FastAPI (dashboard, ejecución, logs)
│   ├── agent.py             # Orquestador: Function Calling con OpenAI
│   ├── tools.py             # Herramientas: inventario, proveedores, agrupación
│   ├── models.py            # Modelos Pydantic (OrdenPedido, ItemPedido...)
│   ├── storage.py           # Persistencia ligera en JSON
│   ├── data/                # Base de datos simulada (inventario, proveedores, órdenes)
│   ├── logs/                # Bitácora de trazabilidad (JSON y texto plano)
│   ├── requirements.txt     # Dependencias de Python
│   └── .env.example         # Variables de entorno
│
├── frontend/
│   ├── index.html           # Dashboard principal (Tablero, Bandeja, Bitácora)
│   ├── styles.css           # UI moderna con efecto Glassmorphism
│   └── app.js               # Lógica de consumo de API y renderizado
│
└── README.md
```

---

## 🧠 Flujo de la Inteligencia Artificial (OpenAI)

El proyecto utiliza la **Chat Completions API con Function Calling** (`gpt-4o-mini`). El agente orquesta el razonamiento consumiendo las siguientes herramientas de lectura:

| Herramienta | Función |
| --- | --- |
| 🔍 `verificar_inventario(seccion)` | Devuelve los ítems de una sección que están por debajo del stock mínimo. |
| 💰 `cotizar_proveedores(item, cantidad)` | Busca cotizaciones reales, devolviendo el proveedor más barato y el más rápido. |
| 📦 `agrupar_por_seccion(items)` | Agrupa los ítems evaluados para estructurar la propuesta de pedido final en formato JSON. |

### 🛡️ Human-in-the-loop (Supervisión Humana)

Esta es una restricción arquitectónica clave: **el agente no tiene herramientas para ejecutar compras**. Toda propuesta nace con estado `"pendiente"`. El flujo se detiene hasta que el administrador presiona "Aprobar" o "Rechazar" en el frontend, previniendo riesgos financieros para la pyme.

---

## 🚀 Guía de Instalación y Uso

Para ejecutar el proyecto localmente, necesitas levantar el backend y el frontend por separado.

### 1. Levantar el Backend (FastAPI)

Abre una terminal, navega a la carpeta `backend` y ejecuta los siguientes comandos:

```bash
# 1. Crear y activar el entorno virtual
python -m venv venv
source venv/bin/activate        # En Windows usa: venv\Scripts\activate

# 2. Instalar las dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# ⚠️ Abre el archivo .env y coloca tu OPENAI_API_KEY real

# 4. Iniciar el servidor
uvicorn main:app --reload --port 8000
```

> *La API estará disponible en `http://localhost:8000` (Docs en `/docs`).*

### 2. Levantar el Frontend

El frontend no requiere dependencias. Abre otra terminal en la carpeta `frontend`:

```bash
python -m http.server 5500
```

> *Abre `http://localhost:5500` en tu navegador para ver el dashboard.*

### 3. Prueba End-to-End

1. Abre el dashboard y visualiza el estado actual del inventario.
2. Haz clic en **"Ejecutar Agente de Compras"**.
3. El agente analizará las 4 secciones y generará las propuestas en la **Bandeja de Pendientes**.
4. Aprueba o rechaza el pedido y revisa cómo toda la lógica y razonamiento del agente queda registrada en la **Bitácora de Trazabilidad**.

---

## 🌍 Impacto y Propósito

- **ODS 8 (Trabajo decente y crecimiento económico):** SmartSupply convierte el proceso reactivo y manual de revisar estantes y cotizar por WhatsApp (que suele tomar ~90 minutos) en un flujo automatizado de 1 minuto. Reduce el tiempo administrativo en más del 90%, liberando al personal para tareas de mayor valor.
- **ODS 9 (Industria, innovación e infraestructura):** Ofrece una infraestructura digital replicable y económica (JSON + FastAPI + LLM) para pymes que no pueden costear sistemas ERP pesados o tradicionales.

---

## 🔮 Próximos Pasos (Evolución)

- [ ] Migrar el orquestador al **OpenAI Agents SDK** usando 4 sub-agentes en paralelo coordinados por un agente supervisor.
- [ ] Conectar `cotizar_proveedores` a APIs reales de distribuidores B2B.
- [ ] Reemplazar la persistencia en JSON por una base de datos PostgreSQL.
- [ ] Implementar notificaciones automáticas vía WhatsApp usando Twilio o Meta API cuando haya órdenes pendientes.

PROXIMO