#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cargador Masivo — Wikipedia API → Base de Conocimiento de Nexus
=================================================================
Extrae definiciones de Wikipedia en español para ~300 temas
organizados por categoría y las guarda como archivos JSON
en data/knowledge/, listos para que Nexus los cargue al iniciar.

Uso:
    python scripts/cargar_wikipedia.py              # Todo
    python scripts/cargar_wikipedia.py --dry-run    # Solo mostrar sin guardar
    python scripts/cargar_wikipedia.py --categoria ciencia  # Solo una categoría

Fuente: Wikipedia REST API (gratis, sin API key)
Formato: JSON compatible con knowledge/loader.py de Nexus
"""

import json
import sys
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# ─── Configuración ────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
USER_AGENT = "NucleoNexus/1.0 (https://github.com/kudawasama/NucleoNexus; aprendizaje local)"
MAX_RETRIES = 2
DELAY_BETWEEN = 0.3  # segundos entre requests (respetuoso con Wikipedia)

# ─── Temas por categoría (~300 en total) ──────────────────────
TEMAS = {
    "ciencia": [
        "Fotosíntesis", "Gravedad", "Evolución biológica", "Célula",
        "Átomo", "Tabla periódica de los elementos", "ADN", "Energía",
        "Ecosistema", "Genética", "Física cuántica", "Relatividad general",
        "Big Bang", "Sistema solar", "Vía Láctea", "Agujero negro",
        "Estrella", "Planeta", "Galaxia", "Universo",
        "Bacteria", "Virus", "Sistema inmunitario", "Vacuna",
        "Neurociencia", "Sinapsis", "Hormona", "Metabolismo",
        "Electricidad", "Magnetismo", "Ondas electromagnéticas", "Espectro electromagnético",
        "Reacción química", "Enlace químico", "PH", "Catalizador",
        "Terremoto", "Volcán", "Placa tectónica", "Atmósfera terrestre",
        "Ciclo del agua", "Efecto invernadero", "Capa de ozono", "Biodiversidad",
        "Mitosis", "Meiosis", "Proteína", "Enzima",
        "Antibiótico", "Fermentación",
    ],
    "historia": [
        "Revolución Francesa", "Revolución Industrial", "Segunda Guerra Mundial",
        "Primera Guerra Mundial", "Guerra Fría", "Imperio romano",
        "Antiguo Egipto", "Civilización maya", "Civilización inca",
        "Renacimiento", "Ilustración", "Edad Media",
        "Descubrimiento de América", "Independencia de Chile", "Revolución Rusa",
        "Caída del Muro de Berlín", "Guerra Civil Española", "Napoleón Bonaparte",
        "Alejandro Magno", "Julio César", "Cleopatra", "Genghis Khan",
        "Colonización española de América", "Revolución cubana", "Apartheid",
        "Martin Luther King", "Nelson Mandela", "Mahatma Gandhi",
        "Imperio otomano", "Guerra de Vietnam",
    ],
    "geografia": [
        "Chile", "Argentina", "Brasil", "México",
        "España", "Francia", "Japón", "China",
        "Estados Unidos", "Canadá", "Australia", "India",
        "Océano Pacífico", "Océano Atlántico", "Mar Mediterráneo",
        "Cordillera de los Andes", "Río Amazonas", "Desierto del Sahara",
        "Amazonia", "Antártida", "Polo Norte",
        "Santiago de Chile", "Buenos Aires", "Ciudad de México",
        "Londres", "París", "Tokio", "Nueva York",
        "Río Nilo", "Monte Everest", "Gran Barrera de Coral",
    ],
    "tecnologia": [
        "Internet", "World Wide Web", "Inteligencia artificial",
        "Aprendizaje automático", "Red neuronal artificial", "Algoritmo",
        "Lenguaje de programación", "Python (lenguaje de programación)",
        "Base de datos", "Sistema operativo", "Linux", "Computadora",
        "Teléfono inteligente", "Robot", "Impresora 3D",
        "Energía solar", "Energía eólica", "Vehículo eléctrico",
        "Blockchain", "Criptomoneda", "Bitcoin",
        "Realidad virtual", "Realidad aumentada", "Internet de las cosas",
        "Ciberseguridad", "Encriptación", "Computación en la nube",
        "Big data", "Red 5G", "Satélite artificial",
        "GPS", "WiFi", "Bluetooth",
    ],
    "cultura_general": [
        "Democracia", "Derechos humanos", "Globalización",
        "Educación", "Universidad", "Método científico",
        "Filosofía", "Ética", "Lógica", "Psicología",
        "Economía", "Capitalismo", "Socialismo", "Comunismo",
        "Religión", "Cristianismo", "Islam", "Budismo",
        "Arte", "Música", "Literatura", "Cine",
        "Nutrición", "Vitaminas", "Proteínas", "Carbohidratos",
        "Reciclaje", "Desarrollo sostenible", "Cambio climático",
        "ONU", "Unión Europea", "Fondo Monetario Internacional",
    ],
    "salud": [
        "Medicina", "Anatomía humana", "Sistema circulatorio",
        "Sistema nervioso", "Sistema digestivo", "Sistema respiratorio",
        "Diabetes mellitus", "Cáncer", "Hipertensión arterial",
        "Obesidad", "Nutrición humana", "Primeros auxilios",
        "Anestesia", "Cirugía", "Radiografía", "Ecografía",
        "Antibiótico", "Penicilina", "Insulina", "Aspirina",
        "Sistema endocrino", "Tiroides", "Páncreas",
        "Colesterol", "Glóbulo rojo", "Glóbulo blanco",
        "Plaqueta", "Sistema linfático", "Alergia",
        "Asma", "Neumonía", "Tuberculosis",
    ],
    "biologia": [
        "Biología", "Taxonomía biológica", "Especie",
        "Selección natural", "Mutación", "Herencia genética",
        "Clonación", "Célula madre", "Microscopio",
        "Hongos", "Protozoo", "Alga",
        "Mamífero", "Reptil", "Anfibio", "Ave",
        "Pez", "Artrópodo", "Molusco", "Anélido",
        "Planta vascular", "Helecho", "Musgo",
        "Ecología", "Cadena trófica", "Depredación",
        "Simbiosis", "Parasitismo", "Extinción masiva",
    ],
    "fisica": [
        "Física", "Mecánica clásica", "Leyes de Newton",
        "Fuerza", "Aceleración", "Masa", "Peso",
        "Trabajo (física)", "Energía cinética", "Energía potencial",
        "Termodinámica", "Entropía", "Teoría de la relatividad",
        "Velocidad de la luz", "Agujero de gusano", "Materia oscura",
        "Energía oscura", "Fisión nuclear", "Fusión nuclear",
        "Óptica", "Refracción", "Lente", "Láser",
        "Sonido (física)", "Efecto Doppler", "Onda",
    ],
    "astronomia": [
        "Astronomía", "Sol", "Mercurio (planeta)", "Venus (planeta)",
        "Tierra", "Marte (planeta)", "Júpiter (planeta)",
        "Saturno (planeta)", "Urano (planeta)", "Neptuno (planeta)",
        "Plutón (planeta enano)", "Cometa", "Asteroide", "Meteorito",
        "Estrella de neutrones", "Supernova", "Nebulosa",
        "Constelación", "Orión (constelación)", "Osa Mayor",
        "Telescopio", "Estación Espacial Internacional",
        "Exploración espacial", "Apolo 11", "Misión Artemisa",
    ],
    "arte": [
        "Pintura", "Escultura", "Arquitectura", "Dibujo",
        "Fotografía", "Danza", "Teatro", "Ópera",
        "Miguel Ángel", "Leonardo da Vinci", "Vincent van Gogh",
        "Pablo Picasso", "Frida Kahlo", "Salvador Dalí",
        "Impresionismo", "Surrealismo", "Cubismo",
        "Renacimiento artístico", "Barroco", "Arte contemporáneo",
        "Patrimonio de la Humanidad", "Museo del Louvre",
    ],
    "economia": [
        "Microeconomía", "Macroeconomía", "Oferta y demanda",
        "Inflación", "Producto interno bruto", "Desempleo",
        "Bolsa de valores", "Mercado financiero", "Banco central",
        "Impuesto", "Comercio internacional", "Tratado de libre comercio",
        "Recesión", "Crecimiento económico", "Deuda pública",
        "Moneda", "Tipo de cambio", "Reserva Federal (Estados Unidos)",
        "Banco Mundial", "Balanza comercial",
    ],
    "derecho": [
        "Derecho", "Constitución", "Poder judicial",
        "Poder legislativo", "Poder ejecutivo", "División de poderes",
        "Derechos humanos", "Derecho penal", "Derecho civil",
        "Contrato", "Propiedad privada", "Derecho laboral",
        "Derecho internacional", "Corte Internacional de Justicia",
        "Hábeas corpus", "Presunción de inocencia", "Juicio (derecho)",
        "Constitución Política de la República de Chile",
    ],
    "linguistica": [
        "Lingüística", "Idioma español", "Idioma inglés",
        "Gramática", "Sintaxis", "Fonética", "Semántica",
        "Dialecto", "Lengua materna", "Bilingüismo",
        "Idioma francés", "Idioma alemán", "Idioma chino mandarín",
        "Idioma japonés", "Idioma portugués", "Latín",
        "Alfabeto", "Escritura", "Etimología",
    ],
    "deportes": [
        "Deporte", "Fútbol", "Baloncesto", "Tenis",
        "Natación", "Atletismo", "Ciclismo", "Boxeo",
        "Béisbol", "Rugby", "Voleibol", "Golf",
        "Juegos Olímpicos", "Copa Mundial de Fútbol",
        "Liga de Campeones de la UEFA", "Fórmula 1",
    ],
    "psicologia": [
        "Conductismo", "Psicoanálisis", "Sigmund Freud",
        "Carl Jung", "Cognitivismo", "Percepción",
        "Aprendizaje", "Emoción", "Motivación",
        "Personalidad", "Trastorno mental", "Depresión",
        "Ansiedad", "Estrés", "Psicoterapia", "Autoestima",
        "Inteligencia emocional", "Sesgo cognitivo",
    ],
}

# ─── Funciones ────────────────────────────────────────────────

def fetch_wikipedia_summary(title: str, lang: str = "es") -> dict | None:
    """Obtiene el resumen de un artículo de Wikipedia vía REST API.

    Returns:
        dict con {title, extract, pageid, url} o None si falla.
    """
    encoded_title = urllib.parse.quote(title)
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Extraer datos relevantes
            return {
                "title": data.get("title", title),
                "extract": data.get("extract", ""),
                "pageid": data.get("pageid"),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # Artículo no encontrado
            if attempt < MAX_RETRIES:
                time.sleep(1)
        except Exception:
            if attempt < MAX_RETRIES:
                time.sleep(1)
    return None


def extract_to_fact(title: str, summary: dict) -> list[str]:
    """Convierte un resumen de Wikipedia en hechos utilizables.

    Devuelve una lista de strings (hechos) — puede ser más de uno
    si el extracto contiene listas o múltiples oraciones sustantivas.
    """
    extract = summary.get("extract", "")
    if not extract or len(extract) < 20:
        return []

    facts = []

    # Hecho principal: "X es/es un/es una ..." (primera oración)
    first_sentence = extract.split(".")[0].strip()
    if len(first_sentence) > 20 and len(first_sentence) < 300:
        # Normalizar: capitalizar y asegurar punto final
        fact = first_sentence[0].upper() + first_sentence[1:]
        if not fact.endswith("."):
            fact += "."
        facts.append(fact)

    # Si el extracto es sustancial, agregar una segunda oración como hecho adicional
    sentences = [s.strip() for s in extract.split(".") if len(s.strip()) > 30]
    if len(sentences) >= 2:
        second = sentences[1].strip()
        if len(second) > 30 and len(second) < 300:
            fact2 = second[0].upper() + second[1:]
            if not fact2.endswith("."):
                fact2 += "."
            # Evitar duplicados aproximados
            if fact2[:50].lower() not in facts[0][:50].lower() if facts else True:
                facts.append(fact2)

    return facts


def save_knowledge_json(category: str, facts: list[dict], dry_run: bool = False):
    """Guarda los hechos en un archivo JSON por categoría."""
    filepath = KNOWLEDGE_DIR / f"{category}.json"

    # Cargar existentes si el archivo ya existe
    existing = []
    existing_texts = set()
    if filepath.exists() and not dry_run:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_texts = {item.get("fact", "") for item in existing}
        except (json.JSONDecodeError, Exception):
            existing = []

    # Agregar solo hechos nuevos (no duplicados)
    added = 0
    for fact in facts:
        fact_text = fact.get("fact", "")
        if fact_text in existing_texts:
            continue
        existing.append(fact)
        existing_texts.add(fact_text)
        added += 1

    if dry_run:
        print(f"   [DRY-RUN] {filepath.name}: {added} nuevos (total sería {len(existing)})")
        return added

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return added


def main():
    dry_run = "--dry-run" in sys.argv
    categoria_filtro = None
    for arg in sys.argv[1:]:
        if arg.startswith("--categoria="):
            categoria_filtro = arg.split("=", 1)[1]
        elif arg == "--categoria":
            idx = sys.argv.index("--categoria")
            if idx + 1 < len(sys.argv):
                categoria_filtro = sys.argv[idx + 1]

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    categorias = [categoria_filtro] if categoria_filtro else list(TEMAS.keys())
    total_facts = 0
    total_topics = 0
    failed_topics = 0

    print("=" * 60)
    print("  CARGADOR MASIVO — Wikipedia → Base de Conocimiento Nexus")
    print("=" * 60)
    if dry_run:
        print("  MODO: DRY-RUN (sin guardar)")
    print()

    for categoria in categorias:
        if categoria not in TEMAS:
            print(f"⚠️  Categoría '{categoria}' no encontrada. Omitiendo.")
            continue

        temas = TEMAS[categoria]
        cat_facts = []
        cat_done = 0
        cat_failed = 0

        print(f"📂 {categoria.upper()} ({len(temas)} temas)")
        print("-" * 40)

        for i, tema in enumerate(temas, 1):
            print(f"  [{i:3d}/{len(temas)}] {tema[:50]:<50s}", end=" ", flush=True)

            summary = fetch_wikipedia_summary(tema)
            time.sleep(DELAY_BETWEEN)

            if summary is None:
                print("❌ (no encontrado)")
                cat_failed += 1
                continue

            facts = extract_to_fact(tema, summary)
            if not facts:
                print("⚠️  (sin extracto util)")
                cat_failed += 1
                continue

            cat_facts.extend([
                {"fact": f, "category": categoria, "source": "wikipedia"}
                for f in facts
            ])
            cat_done += 1
            print(f"✓ ({len(facts)} hecho{'s' if len(facts)>1 else ''})")

        # Guardar esta categoría
        if cat_facts:
            added = save_knowledge_json(categoria, cat_facts, dry_run=dry_run)
            total_facts += added
            total_topics += cat_done
            failed_topics += cat_failed
            print(f"  ✅ {categoria}: {added} hechos nuevos guardados "
                  f"({cat_done}/{len(temas)} temas OK, {cat_failed} fallidos)")
        else:
            print(f"  ⚠️  {categoria}: 0 hechos generados")
            failed_topics += cat_failed
        print()

    print("=" * 60)
    print(f"  RESUMEN: {total_facts} hechos de {total_topics} temas")
    if failed_topics:
        print(f"  {failed_topics} temas fallidos (probablemente sin artículo en Wikipedia ES)")
    if dry_run:
        print("  MODO DRY-RUN — no se guardó nada.")
    else:
        print(f"  Archivos guardados en: {KNOWLEDGE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
