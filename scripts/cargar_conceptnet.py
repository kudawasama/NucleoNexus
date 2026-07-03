#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cargador Masivo — ConceptNet API → Base de Conocimiento de Nexus
==================================================================
Extrae relaciones semánticas de ConceptNet (red de conocimiento
multilingüe gratuita) y las guarda como hechos en formato JSON.

ConceptNet conecta conceptos con relaciones como:
  "perro" -> "IsA" -> "animal"
  "sol" -> "HasProperty" -> "caliente"
  "cuchillo" -> "UsedFor" -> "cortar"

Uso:
    python scripts/cargar_conceptnet.py              # Todo (~500 hechos)
    python scripts/cargar_conceptnet.py --dry-run    # Solo mostrar sin guardar

Fuente: ConceptNet API (gratis, sin API key, rate limit 120 req/min)
"""

import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# ─── Configuración ────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
USER_AGENT = "NucleoNexus/1.0 (aprendizaje local)"
OUTPUT_FILE = KNOWLEDGE_DIR / "conceptnet.json"

# Rate limit de ConceptNet: ~120 req/min → 1 cada 0.5s seguro
DELAY_BETWEEN = 0.5
MAX_RELATIONS_PER_CONCEPT = 5
MAX_RETRIES = 2

# ─── Conceptos semilla (~100, cubren dominios variados) ───────
# Usamos labels en español; ConceptNet los resuelve vía /c/es/ o /c/en/
CONCEPTOS = [
    # Naturaleza y ciencia
    "agua", "fuego", "aire", "tierra", "sol", "luna", "estrella",
    "planta", "árbol", "flor", "animal", "perro", "gato", "pájaro",
    "pez", "insecto", "fruta", "semilla", "océano", "montaña",
    "lluvia", "nieve", "viento", "nube", "trueno",
    "oxígeno", "carbono", "hierro", "oro", "sal",

    # Cuerpo humano y salud
    "corazón", "cerebro", "pulmón", "hígado", "riñón",
    "sangre", "hueso", "músculo", "piel", "ojo",
    "oído", "mano", "pie", "diente",
    "enfermedad", "medicina", "vacuna", "virus", "bacteria",

    # Alimentos
    "pan", "leche", "queso", "huevo", "carne",
    "arroz", "azúcar", "sal", "aceite", "vino",

    # Tecnología
    "computadora", "teléfono", "internet", "robot", "software",
    "electricidad", "motor", "batería", "cámara", "pantalla",
    "satélite", "avión", "automóvil", "bicicleta", "tren",

    # Sociedad
    "escuela", "hospital", "biblioteca", "museo", "iglesia",
    "gobierno", "ley", "juez", "policía", "dinero",
    "idioma", "libro", "periódico", "mapa", "bandera",

    # Conceptos abstractos
    "amor", "felicidad", "tristeza", "miedo", "valentía",
    "inteligencia", "memoria", "sueño", "idea", "verdad",
    "tiempo", "espacio", "número", "color", "sonido",
    "música", "arte", "belleza", "libertad", "justicia",
]

# ─── Mapeo de relaciones a español ────────────────────────────
REL_ES = {
    "IsA": "es un tipo de",
    "HasProperty": "tiene la propiedad de ser",
    "CapableOf": "es capaz de",
    "UsedFor": "se usa para",
    "PartOf": "es parte de",
    "HasA": "tiene",
    "MadeOf": "está hecho de",
    "AtLocation": "se encuentra en",
    "Causes": "causa",
    "HasSubevent": "implica",
    "HasPrerequisite": "requiere",
    "MotivatedByGoal": "se motiva por",
    "Desires": "desea",
    "CreatedBy": "es creado por",
    "Synonym": "es sinónimo de",
    "Antonym": "es lo opuesto de",
    "DerivedFrom": "deriva de",
    "EtymologicallyRelatedTo": "está relacionado etimológicamente con",
    "RelatedTo": "está relacionado con",
    "FormOf": "es una forma de",
    "SimilarTo": "es similar a",
}


def fetch_conceptnet_edges(concept: str, lang: str = "es") -> list[dict]:
    """Obtiene relaciones de ConceptNet para un concepto.

    Prueba primero con label en español (/c/es/), luego en inglés.
    """
    encoded = urllib.parse.quote(concept.lower())
    url = (
        f"https://api.conceptnet.io/query?"
        f"node=/c/{lang}/{encoded}&limit=20"
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("edges", [])
        except Exception:
            if attempt < MAX_RETRIES:
                time.sleep(1)
    return []


def edge_to_fact_es(edge: dict) -> str | None:
    """Convierte un edge de ConceptNet a un hecho en español.

    Prioriza surfaceText en español; si no hay, construye con las labels.
    """
    rel = edge.get("rel", {}).get("label", "")
    start = edge.get("start", {})
    end = edge.get("end", {})

    # Obtener labels en español (o inglés como fallback)
    start_label = start.get("label", "")
    end_label = end.get("label", "")

    if not start_label or not end_label:
        return None

    # Intentar surfaceText en español
    surface = edge.get("surfaceText", "")
    if surface and any(c in surface for c in "áéíóúñü"):
        # surfaceText en español detectado — limpiar [[corchetes]]
        clean = surface.replace("[[", "").replace("]]", "")
        if len(clean) > 15 and len(clean) < 300:
            return clean[0].upper() + clean[1:] + "."

    # Construir con la relación
    rel_es = REL_ES.get(rel, f"está relacionado con")
    if rel_es:
        # Elegir el orden correcto según la relación
        fact = f"{start_label} {rel_es} {end_label}."
        if len(fact) > 15 and len(fact) < 300:
            return fact

    return None


def main():
    dry_run = "--dry-run" in sys.argv

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  CARGADOR MASIVO — ConceptNet → Base de Conocimiento Nexus")
    print("=" * 60)
    if dry_run:
        print("  MODO: DRY-RUN (sin guardar)")
    print(f"  Conceptos semilla: {len(CONCEPTOS)}")
    print()

    all_facts = []
    existing_texts = set()
    conceptos_ok = 0
    conceptos_fail = 0
    total_edges = 0

    # Cargar existentes para evitar duplicados
    if OUTPUT_FILE.exists() and not dry_run:
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_texts = {item.get("fact", "") for item in existing}
            all_facts = existing.copy()
            print(f"  (Archivo existente: {len(existing)} hechos previos)")
        except (json.JSONDecodeError, Exception):
            pass

    for i, concepto in enumerate(CONCEPTOS, 1):
        print(f"  [{i:3d}/{len(CONCEPTOS)}] {concepto:<25s}", end=" ", flush=True)

        edges = fetch_conceptnet_edges(concepto)
        time.sleep(DELAY_BETWEEN)

        if not edges:
            print("⚠️  (sin resultados)")
            conceptos_fail += 1
            continue

        facts_from_concept = 0
        for edge in edges[:MAX_RELATIONS_PER_CONCEPT]:
            fact = edge_to_fact_es(edge)
            if fact and fact not in existing_texts:
                all_facts.append({
                    "fact": fact,
                    "category": "conceptnet",
                    "source": "conceptnet",
                })
                existing_texts.add(fact)
                facts_from_concept += 1
                total_edges += 1

        if facts_from_concept > 0:
            conceptos_ok += 1
            print(f"✓ ({facts_from_concept} relaciones)")
        else:
            conceptos_fail += 1
            print("⚠️  (sin relaciones utiles)")

    print()
    print("-" * 40)
    print(f"  Resultados: {total_edges} hechos de {conceptos_ok} conceptos")
    print(f"  Fallidos: {conceptos_fail} conceptos")
    print(f"  Total acumulado: {len(all_facts)} hechos")

    if dry_run:
        print("  MODO DRY-RUN — no se guardó nada.")
    else:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_facts, f, indent=2, ensure_ascii=False)
        print(f"  ✅ Guardado en: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
