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

```bash
cd NucleoNexus
python main.py
```

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
| `/export` | Exportar estado JSON |
| `/clear`  | Limpiar pantalla |
| `/reset`  | Reiniciar estado |
| `/exit`   | Salir |

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

### Roadmap tecnico

1. **Proto (ahora)**: Simbolico + TF-IDF + SQLite ← ESTAMOS AQUI
2. **Basico**: Mejora de patrones, mas skills builtin
3. **Intermedio**: Integracion con SLM local (Qwen2.5-0.5B)
4. **Avanzado**: API REST, plugin system, web UI
5. **Pro**: Multi-agente, distributed memory, auto-skill creation

---

## Licencia

MIT — Construido por Jose Cespedes para el ecosistema ContanoPet.
