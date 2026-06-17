"""
Núcleo Nexus — Generador de Guías (Notebook Guide)
===================================================
Genera resúmenes ejecutivos, FAQ, timeline y conceptos clave
a partir de documentos ingeridos en memoria.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger("nexus.knowledge.guide")

# Prompt base para generación de guías
GUIDE_SYSTEM_PROMPT = """Eres un analista de documentos experto.
Genera guías estructuradas basadas SOLO en el contenido del documento proporcionado.
NO inventes información que no esté en el documento.
Responde SIEMPRE en español.

Genera los siguientes formatos:

1. BRIEFING (resumen ejecutivo):
   - Propósito del documento
   - 3-5 puntos clave
   - Conclusión principal

2. FAQ (3-5 preguntas frecuentes):
   Cada pregunta con su respuesta basada en el documento.

3. CONCEPTOS CLAVE:
   Lista de términos importantes con definición breve.

4. TIMELINE (si aplica):
   Eventos en orden cronológico encontrados en el documento.

Formato de respuesta:
{
  "titulo": "Título del documento",
  "briefing": "resumen ejecutivo...",
  "faq": [{"pregunta": "...", "respuesta": "..."}],
  "conceptos": [{"termino": "...", "definicion": "..."}],
  "timeline": [{"fecha": "...", "evento": "..."}]
}
"""


def generate_guide(slm, memory, titulo: str = "Documento",
                   max_chunks: int = 10) -> Optional[dict]:
    """Genera una guía completa a partir de un documento en memoria.
    
    Args:
        slm: Instancia de SLMBackend (OpenCode)
        memory: Instancia de NexusMemory
        titulo: Título del documento a analizar
        max_chunks: Máximo de chunks a incluir
        
    Returns:
        Dict con briefing, faq, conceptos, timeline o None si falla
    """
    # Buscar chunks del documento en memoria
    facts = memory.query_knowledge(titulo, top_k=max_chunks)
    if not facts:
        logger.warning(f"No se encontraron chunks para '{titulo}'")
        return None
    
    # Construir el contexto con los chunks
    lines = [f"=== DOCUMENTO: {titulo} ==="]
    for i, fact in enumerate(facts, 1):
        text = fact.get("text", "")
        # Limpiar prefijo [Documento] si existe
        text = text.replace(f"[{titulo}] ", "", 1)
        lines.append(f"\n--- Sección {i} ---\n{text[:500]}")
    lines.append("\n=== FIN DEL DOCUMENTO ===")
    
    context = "\n".join(lines)
    
    # Generar guía con el SLM
    logger.info(f"Generando guía para '{titulo}' ({len(facts)} chunks)...")
    result = slm.generate(
        context,
        system_prompt=GUIDE_SYSTEM_PROMPT,
        structured=False
    )
    
    if not result:
        logger.warning("SLM no generó respuesta para la guía")
        return None
    
    # Intentar parsear como JSON
    try:
        guide = json.loads(result)
        return guide
    except json.JSONDecodeError:
        # Si no es JSON válido, devolver como texto plano
        logger.info("La guía no es JSON válido, devolviendo texto")
        return {
            "titulo": titulo,
            "briefing": result[:1000],
            "faq": [],
            "conceptos": [],
            "timeline": [],
            "_raw": True
        }


def generate_faq(slm, topic: str, memory,
                 num_questions: int = 3) -> Optional[list]:
    """Genera FAQ sobre un tema específico usando memoria disponible.
    
    Args:
        slm: Instancia de SLMBackend
        topic: Tema sobre el cual generar preguntas
        memory: Instancia de NexusMemory
        num_questions: Número de preguntas a generar
        
    Returns:
        Lista de dicts {pregunta, respuesta} o None
    """
    facts = memory.query_knowledge(topic, top_k=5)
    if not facts:
        return None
    
    context = "\n".join(f"- {f.get('text', '')[:200]}" for f in facts)
    
    prompt = f"""Basado en esta información:
{context}

Genera {num_questions} preguntas frecuentes con sus respuestas.
Formato JSON: [{{"pregunta": "...", "respuesta": "..."}}]
Responde solo con el JSON, nada más."""
    
    result = slm.generate(prompt, structured=False)
    if not result:
        return None
    
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return None
