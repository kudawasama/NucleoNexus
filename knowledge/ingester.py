"""
Núcleo Nexus — Ingestor de Documentos
======================================
Procesa documentos de texto: chunking, almacenamiento en memoria,
y recuperación para generación de guías.
"""
import re
import logging
from typing import List, Optional

logger = logging.getLogger("nexus.knowledge.ingester")

# Tamaño de chunk: ~500 tokens (~2000 chars)
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[dict]:
    """Divide un texto en chunks superpuestos.
    
    Args:
        text: Texto a dividir
        chunk_size: Tamaño máximo de cada chunk en caracteres
        overlap: Superposición entre chunks en caracteres
        
    Returns:
        Lista de dicts con {index, text, tokens_estimados}
    """
    if not text or not text.strip():
        return []
    
    # Limpiar el texto
    text = re.sub(r'\s+', ' ', text).strip()
    
    chunks = []
    start = 0
    index = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # Intentar cortar en límite de párrafo u oración
        if end < len(text):
            # Buscar último punto y espacio antes del límite
            cut = max(
                text.rfind('\n\n', start, end),
                text.rfind('. ', start, end),
                text.rfind('.\n', start, end),
                text.rfind('? ', start, end),
                text.rfind('! ', start, end),
            )
            if cut > start + chunk_size // 2:
                end = cut + 1
        
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "index": index,
                "text": chunk_text,
                "tokens_estimados": len(chunk_text) // 4,
            })
            index += 1
        
        start = end - overlap if end < len(text) else len(text)
    
    logger.info(f"Documento dividido en {len(chunks)} chunks")
    return chunks


def ingest_text(text: str, memory, titulo: str = "Documento") -> int:
    """Ingiere un texto completo en el sistema de memoria.
    
    Cada chunk se almacena como un hecho en memoria semántica
    con categoría "documento" y el título como referencia.
    
    Args:
        text: Texto a ingerir
        memory: Instancia de NexusMemory
        titulo: Título descriptivo del documento
        
    Returns:
        Cantidad de chunks almacenados
    """
    chunks = chunk_text(text)
    count = 0
    
    for chunk in chunks:
        # Almacenar con referencia al documento original
        fact = f"[{titulo}] {chunk['text'][:300]}"
        memory.learn_fact(
            fact,
            category="documento",
            confidence=0.5,
            source=f"ingesta:{titulo}"
        )
        count += 1
    
    # También almacenar referencia del documento completo
    memory.learn_fact(
        f"Documento: {titulo} ({len(chunks)} secciones, {len(text)} caracteres)",
        category="documento",
        confidence=0.8,
        source=f"ingesta:{titulo}"
    )
    
    logger.info(f"Ingerido '{titulo}': {count} chunks en memoria")
    return count
