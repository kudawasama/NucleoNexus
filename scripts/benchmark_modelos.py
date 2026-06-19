#!/usr/bin/env python3
"""
Benchmark de Modelos para NucleoNexus
======================================
Compara modelos locales (Ollama) en 5 categorías:
  1. Conversación cotidiana (español)
  2. Generación de código (Python)
  3. Tool calling / Function calling
  4. Razonamiento lógico / matemático
  5. Comprensión de contexto largo
"""

import json
import time
import subprocess
import sys
from datetime import datetime

# Modelos a evaluar (los que ya están + los que se están bajando)
MODELOS = [
    "hermes3:3b",
    "qwen2.5:3b",
    "llama3.2:latest",
    "qwen2.5:0.5b",
    "llama3.2:1b",
]

# Modelos que se agregarán si están disponibles
MODELOS_EXTRA = ["qwen3:4b", "granite4:3b"]

# ─── Prompts de evaluación ────────────────────────────────────

PRUEBAS = {
    "1_vida_cotidiana": {
        "descripcion": "Conversación cotidiana en español",
        "prompts": [
            "¿Qué me recomiendas para cocinar esta noche? Tengo pollo, arroz y verduras. Responde en español.",
            "Explícame qué es el efecto invernadero como si tuviera 12 años. En español.",
            "Estoy pensando en aprender a tocar guitarra. ¿Qué me aconsejas? Respuesta corta, en español.",
        ],
        "evalua": ["español_correcto", "utilidad", "naturalidad"],
    },
    "2_codigo": {
        "descripcion": "Generación de código Python",
        "prompts": [
            "Escribe una función en Python que reciba una lista de números y devuelva el segundo más grande sin usar sorted(). Solo código, sin explicación.",
            "Escribe un decorador en Python que mida el tiempo de ejecución de una función. Solo código.",
            "Corrige este código:\ndef fibonacci(n):\n    if n = 0: return 0\n    if n == 1: return 1\n    return fibonacci(n-1) + fibonacci(n-2)\n\nResponde solo con el código corregido.",
        ],
        "evalua": ["correccion", "eficiencia", "legibilidad"],
    },
    "3_tool_calling": {
        "descripcion": "Tool calling / Function calling",
        "prompts": [
            """Eres un asistente con acceso a herramientas. Responde con un JSON de acción.

Herramientas disponibles:
- get_weather(ciudad: str) -> dict
- calculate(expresion: str) -> float
- search_files(patron: str) -> list
- web_search(query: str) -> list

Usuario: "¿Qué temperatura hace en Santiago?"

Responde SOLO con JSON: {"tool": "...", "args": {...}}""",

            """Mismas herramientas. Usuario: "Calcula 15% de 850 más 200"
Responde SOLO con JSON: {"tool": "...", "args": {...}}""",

            """Mismas herramientas. Usuario: "Busca en internet cómo hacer pan casero"
Responde SOLO con JSON: {"tool": "...", "args": {...}}""",
        ],
        "evalua": ["herramienta_correcta", "args_correctos", "formato_json"],
    },
    "4_razonamiento": {
        "descripcion": "Razonamiento lógico y matemático",
        "prompts": [
            "Si un tren sale de A a las 8:00 a 60 km/h y otro sale de B a las 8:30 a 90 km/h hacia A, y la distancia es 300 km, ¿a qué hora se encuentran? Explica tu razonamiento.",
            "En una habitación hay 5 personas. Cada una saluda a las otras exactamente una vez. ¿Cuántos saludos hubo en total? Explica paso a paso.",
            "Si todos los gatos son mamíferos, y algunos mamíferos vuelan, ¿podemos concluir que algunos gatos vuelan? Razona tu respuesta.",
        ],
        "evalua": ["razonamiento", "respuesta_correcta", "claridad"],
    },
    "5_contexto": {
        "descripcion": "Comprensión de contexto",
        "prompts": [
            """Lee esta información:

Persona: María García
Edad: 34 años
Profesión: Ingeniera de software
Ciudad: Barcelona
Hobbies: Escalada, fotografía, cocina italiana
Mascota: Un gato llamado "Neo"
Proyecto actual: App de recetas con IA

Basado en esta información, responde: ¿Qué tipo de app está desarrollando María?""",

            """Contexto:
- La reunión es el viernes a las 3pm
- Asistirán: Carlos (marketing), Ana (desarrollo), Luis (diseño)
- Tema: Rediseño de la landing page
- Ana tiene un conflicto hasta las 3:30pm
- Luis necesita las especificaciones antes del jueves

Pregunta: ¿A qué hora puede realmente empezar la reunión con todos presentes?""",
        ],
        "evalua": ["comprension", "precision", "contexto_utilizado"],
    },
}


def check_model_available(model: str) -> bool:
    """Verifica si el modelo está disponible en Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        return model in result.stdout
    except Exception:
        return False


def run_ollama(model: str, prompt: str, system: str = "", timeout: int = 120) -> dict:
    """Ejecuta un prompt contra Ollama y mide tiempo."""
    t_start = time.time()

    system_arg = []
    if system:
        system_arg = ["--system", system]

    try:
        result = subprocess.run(
            ["ollama", "run", model, *system_arg, prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        t_end = time.time()
        duration_ms = (t_end - t_start) * 1000

        return {
            "response": result.stdout.strip(),
            "error": result.stderr.strip() if result.returncode != 0 else "",
            "duration_ms": round(duration_ms, 1),
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "response": "",
            "error": "TIMEOUT",
            "duration_ms": timeout * 1000,
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "response": "",
            "error": str(e),
            "duration_ms": 0,
            "exit_code": -1,
        }


def main():
    print("=" * 70)
    print("  BENCHMARK DE MODELOS PARA NUCLEONEXUS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Detectar modelos disponibles
    disponibles = [m for m in MODELOS if check_model_available(m)]
    for m in MODELOS_EXTRA:
        if check_model_available(m):
            disponibles.append(m)

    print(f"\n📦 Modelos disponibles: {len(disponibles)}")
    for m in disponibles:
        print(f"   ✅ {m}")
    faltantes = [m for m in MODELOS + MODELOS_EXTRA if m not in disponibles]
    if faltantes:
        print(f"\n⏳ Modelos aún descargando: {len(faltantes)}")
        for m in faltantes:
            print(f"   ⏳ {m}")

    if not disponibles:
        print("\n❌ No hay modelos disponibles. Espera a que terminen las descargas.")
        return

    # Ejecutar benchmark
    resultados = {}

    total_pruebas = sum(len(p["prompts"]) for p in PRUEBAS.values())
    total_ejecuciones = total_pruebas * len(disponibles)
    ejecucion = 0

    print(f"\n🚀 Ejecutando {total_ejecuciones} pruebas...\n")

    for cat_key, cat_data in PRUEBAS.items():
        print(f"📋 {cat_data['descripcion']}")
        print(f"   {len(cat_data['prompts'])} prompts × {len(disponibles)} modelos")
        print()

        for i, prompt in enumerate(cat_data["prompts"]):
            prompt_short = prompt[:80].replace("\n", " ")
            print(f"   [{cat_key}.{i+1}] {prompt_short}...")

            for modelo in disponibles:
                ejecucion += 1
                pct = ejecucion / total_ejecuciones * 100
                print(f"      🧠 {modelo:<20}", end=" ", flush=True)

                result = run_ollama(modelo, prompt)
                key = f"{cat_key}_{i+1}"

                if key not in resultados:
                    resultados[key] = {
                        "categoria": cat_key,
                        "descripcion": cat_data["descripcion"],
                        "prompt": prompt,
                    }

                resultados[key][modelo] = {
                    "response": result["response"][:500],
                    "response_full_len": len(result["response"]),
                    "duration_ms": result["duration_ms"],
                    "error": result["error"],
                }

                if result["error"]:
                    print(f"❌ {result['error'][:40]}")
                else:
                    print(f"✅ {result['duration_ms']:.0f}ms | {len(result['response'])} chars")

    # ─── Guardar resultados ───────────────────────────────────
    output_file = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Resumen por modelo
    resumen = {}
    for modelo in disponibles:
        tiempos = []
        errores = 0
        chars_total = 0
        for key, data in resultados.items():
            if modelo in data:
                r = data[modelo]
                if r["error"]:
                    errores += 1
                else:
                    tiempos.append(r["duration_ms"])
                    chars_total += r["response_full_len"]

        resumen[modelo] = {
            "pruebas_completadas": len(tiempos),
            "errores": errores,
            "tiempo_promedio_ms": round(sum(tiempos) / len(tiempos), 1) if tiempos else 0,
            "tiempo_total_ms": round(sum(tiempos), 1),
            "chars_generados": chars_total,
        }

    output = {
        "metadata": {
            "fecha": datetime.now().isoformat(),
            "modelos_evaluados": disponibles,
            "pruebas_por_categoria": {k: len(v["prompts"]) for k, v in PRUEBAS.items()},
        },
        "resumen": resumen,
        "resultados": resultados,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # ─── Mostrar resumen ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("  📊 RESUMEN FINAL")
    print("=" * 70)
    print(f"\n{'Modelo':<22} {'Pruebas':>8} {'Errores':>8} {'Tiempo prom':>12} {'Total':>10}")
    print("-" * 62)
    for modelo in disponibles:
        r = resumen[modelo]
        print(f"{modelo:<22} {r['pruebas_completadas']:>8} {r['errores']:>8} {r['tiempo_promedio_ms']:>9.0f}ms {r['tiempo_total_ms']:>7.0f}ms")

    print(f"\n💾 Resultados guardados en: {output_file}")
    print("✅ Benchmark completo.")


if __name__ == "__main__":
    main()
