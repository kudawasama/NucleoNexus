# Nucleo Nexus

**IA Ultra-Ligera con Aprendizaje Incremental**

```
╔══════════════════════════════════╗
║     ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗    ║
║     ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝    ║
║     ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗    ║
║     ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║    ║
║     ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║    ║
║     ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ║
╚══════════════════════════════════╝
```

## Filosofia

Nexus es un sistema de IA diseñado para **aprender incrementalmente** sin necesidad de GPU, servidores en la nube, ni hardware de ultima generacion.

**Principios arquitectonicos:**

### 1. Separacion estricta: Logica vs Cognicion
El motor de estado (JSON persistente) y las rules de negocio estan **totalmente separados** de la capa cognitiva (la IA). La IA nunca calcula nada — solo consume estado y genera respuestas.

### 2. Backend intercambiable
- **Modo Simbolico** (default): Sin modelo de IA. Usa pattern matching, TF-IDF y reglas. Funciona en cualquier PC.
- **Modo SLM**: Conecta con modelos locales (Qwen2.5, Phi-2, Llama 3.2) via Ollama o llama.cpp. ~500 MB de RAM.
- **Modo Hibrido**: Combinacion de ambos.

### 3. Aprendizaje por persistencia
Nexus NO reentrena sus pesos. "Aprende" acumulando:
- **Memoria Episodica**: Registro de interacciones
- **Memoria Semantica**: Hechos y conceptos con confianza
- **Memoria Procedimental**: Patrones de respuesta efectivos

### 4. Skills como funciones de codigo
Cada habilidad nueva es simplemente una funcion de Python registrada como Skill. Function Calling nativo sin necesidad de OpenAI.

### 5. Evolucion por fases
Nexus comienza como **Proto** y evoluciona hasta **Pro** basado en interacciones:
- Proto (0-10) → Basico (10-50) → Intermedio (50-200) → Avanzado (200-500) → Pro (500+)
- Cada fase desbloquea mayor complejidad en las respuestas.

---

## Arquitectura

```
+---------------------------------------------------------------+
|                     INTERFAZ                                   |
|             (CLI / API / Web)                                 |
+---------------------------------------------------------------+
|                   CAPA COGNITIVA                               |
|  +----------+  +----------+  +-----------------------------+  |
|  | Simbolico |  |   SLM    |  | Inyector de               |  |
|  | (default) |  | (Qwen,   |  | Contexto                   |  |
|  |           |  |  Phi...) |  | Dinamico                   |  |
|  +----------+  +----------+  +-----------------------------+  |
+---------------------------------------------------------------+
|                  SKILLS / ACCIONES                             |
|      (Function Calling . Registry . Builtins)                 |
+---------------------------------------------------------------+
|                MOTOR DE ESTADO                                 |
|   (JSON persistente . Metricas . Fases)                      |
+---------------------------------------------------------------+
|                MEMORIA PERSISTENTE                             |
|  +----------+  +----------+  +-----------------------------+  |
|  |Epi-sodica|  |Semantica |  |Procedimental               |  |
|  | (Que     |  | (Hechos) |  | (Como hacer)               |  |
|  |  paso)   |  |          |  |                             |  |
|  +----------+  +----------+  +-----------------------------+  |
|              SQLite + TF-IDF                                   |
+---------------------------------------------------------------+
|              SISTEMA (archivos, DB)                            |
+---------------------------------------------------------------+
```

---

## Estructura del Proyecto

```
NucleoNexus/
├── engine/              # Motor de estado y acciones
│   ├── state.py         # Estado persistente en JSON
│   └── actions.py       # Sistema de Function Calling
├── memory/              # Memoria persistente (SQLite + TF-IDF)
│   ├── store.py         # Fachada unificada
│   ├── episodic.py      # Recuerdos de interacciones
│   ├── semantic.py      # Hechos y conceptos
│   └── procedural.py    # Patrones aprendidos
├── cognition/           # Capa cognitiva
│   ├── symbolic.py      # Motor simbolico (sin modelo)
│   ├── slm.py           # Backend para SLM local
│   └── context.py       # Inyector de contexto dinamico
├── skills/              # Skills modulares
│   ├── registry.py      # Registro de skills
│   └── builtins/        # Skills nativas
│       └── system_skill.py
├── interface/           # Interfaces de usuario
│   └── cli.py           # Terminal interactivo
├── data/                # Datos persistentes
│   ├── memory/          # Base de datos SQLite
│   ├── state/           # Estado JSON
│   └── logs/            # Logs del sistema
├── config.py            # Configuracion central
├── main.py              # Punto de entrada
├── requirements.txt     # Dependencias
└── README.md            # Este archivo
```

---

## Requisitos

- **Python 3.10+** (solo stdlib para modo basico)
- **Sin GPU, sin CUDA, sin servidores**
- ~50 MB de RAM en modo simbolico
- ~500 MB de RAM si activas SLM local

## Inicio Rapido

### En Windows (PowerShell):
```powershell
# Ejecuta el launcher optimizado (resuelve rutas y previene errores de Unicode automáticamente)
.\nexus.ps1
```

### En Linux / Mac / Unix:
```bash
./nexus
```

### Ejecución Directa con Python:
```bash
python main.py
```

---

## Capacidades de Memoria y Optimización (Fase Pro)

A partir de la versión **v0.1.0+build.96**, el motor semántico de Nexus implementa capacidades avanzadas de optimización local y robustez:

* **Vectorización Asíncrona (Fase 1)**: La llamada a `learn_fact` guarda hechos con `embedding = NULL` de forma instantánea. Un hilo worker en segundo plano (demonio) se encarga de vectorizar los hechos utilizando Ollama, eliminando cualquier bloqueo o lag en el chat del usuario.
* **Deduplicación Semántica (Fase 2A)**: El worker asíncrono compara la similitud de coseno del nuevo vector frente a los hechos existentes. Si la similitud supera el **88%** ($sim \ge 0.88$), el hecho se consolida:
  * Se incrementa la confianza (`confidence`) del hecho original en `+0.1` (máximo `1.0`).
  * Se incrementa el contador de accesos (`access_count`).
  * Se elimina el registro duplicado recién insertado para mantener la base de datos limpia de redundancias.
* **Decaimiento Temporal y Frecuencia**: Las búsquedas en la memoria semántica aplican un factor de decaimiento exponencial basado en el tiempo de desuso del hecho, ponderando también la frecuencia de uso:
  $$\text{Relevancia} = \text{Similitud} \times \max(0.2, 0.99^{\Delta t\_dias}) \times (1.0 + 0.1 \times \log(\text{access\_count} + 1))$$

---

## Interfaz de Usuario (UX) Premium

La consola de Nexus ha sido rediseñada para ofrecer una experiencia interactiva sin dependencias externas:

* **Sugerencias Inline en Tiempo Real**: Al escribir el carácter `/`, se listan dinámicamente debajo del prompt las sugerencias de comandos que coinciden con tu entrada.
* **Autocompletado con Tab**: Presionar la tecla `Tab` autocompleta el comando. Al presionarla consecutivamente, rotarás de forma cíclica entre todas las coincidencias válidas.
* **Navegación del Historial**: Soporte nativo para usar las flechas **Arriba** y **Abajo** del teclado para desplazarse por el historial de inputs.
* **Diseño Anti-Descuadre**: Logotipo ASCII minimalista flotante y barra de estado de metadatos unificada en una sola línea compacta de alta estética, adaptándose a cualquier ancho de consola.

---

## Comandos de la CLI

| Comando | Descripcion |
|---------|-------------|
| `/help`   | Muestra ayuda |
| `/status` | Estado del sistema |
| `/stats`  | Estadisticas de memoria |
| `/fase`   | Progreso de evolucion |
| `/memoria` | Recuerdos recientes |
| `/hechos` | Hechos aprendidos |
| `/skills` | Skills cargadas |
| `/personalidad` | Ver/cambiar personalidad |
| `/backend` | Cambiar modo (symbolic/slm) |
| `/model` | Gestionar modelos y backends |
| `/export` | Exportar estado JSON |
| `/update` | git pull desde GitHub |
| `/clear`  | Limpiar pantalla |
| `/reset`  | Reiniciar estado |
| `/exit`   | Salir |
| `/agent <tarea>` | Encadenar herramientas (ReAct) |

## Ensenar cosas a Nexus

Nexus aprende de forma natural mientras conversas:

- `"aprende que Python es un lenguaje de programacion"`
- `"Nexus, recuerda que mi nombre es Jose"`
- Cualquier pregunta que hagas, Nexus la registra como patron

---

## Plan de Evolucion a Ultra Pro

| Fase | Interacciones | Capacidades |
|------|--------------|-------------|
| Proto | 0-10 | Respuestas basicas, pattern matching |
| Basico | 10-50 | Skills activas, personalidad definida |
| Intermedio | 50-200 | Razonamiento multi-turno, memoria activa |
| Avanzado | 200-500 | RAG completo, aprendizaje autodirigido |
| Pro | 500+ | Creatividad plena, analisis profundo |

### Roadmap tecnico completado

1. **Fase 1 (Completado)**: Desacoplamiento de embeddings y factor de decaimiento en memoria semántica.
2. **Fase 2A (Completado)**: Deduplicación semántica asíncrona de fondo ($sim \ge 0.88$) y reforzamiento de confianza.
3. **UX Interactiva (Completado)**: Autocompletado de comandos inline y soporte de historial nativo en Windows (`msvcrt`).

---

## Licencia

MIT — Construido por Jose Cespedes para el ecosistema ContanoPet.
