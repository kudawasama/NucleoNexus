"""
Núcleo Nexus — Memoria Semántica
=================================
Almacenamiento de hechos, conceptos y relaciones.
Cada hecho tiene un nivel de confianza que aumenta con la repetición.
"""

import sqlite3
import json
import time
import logging

logger = logging.getLogger("nexus.memory.semantic")


class SemanticMemory:
    """Memoria semántica — hechos y conceptos con confianza."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def _init_table(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fact        TEXT UNIQUE NOT NULL,
                category    TEXT DEFAULT 'general',
                confidence  REAL DEFAULT 0.5,
                source      TEXT,
                created_at  REAL,
                updated_at  REAL,
                access_count INTEGER DEFAULT 0,
                embedding   BLOB
            )
        """)
        # Migracion: agregar columna embedding si no existe
        try:
            cur.execute("ALTER TABLE semantic ADD COLUMN embedding BLOB")
            self.conn.commit()
            logger.info("Tabla semantic migrada: columna embedding agregada")
        except sqlite3.OperationalError:
            # La columna ya existe
            pass
        self.conn.commit()

    def learn_fact(self, fact: str, category: str = "general",
                   confidence: float = 0.5, source: str = None,
                   with_embedding: bool = True) -> bool:
        """Aprende un hecho. Si ya existe, refuerza confianza.

        Args:
            fact: Texto del hecho
            category: Categoria (default: general)
            confidence: Confianza 0-1
            source: Origen del hecho
            with_embedding: Si True, genera embedding (default True).
                False para cargas masivas donde embeddings se generan despues.

        Si el modelo de embeddings esta disponible, tambien guarda
        el vector del hecho para busqueda semantica.
        """
        cur = self.conn.cursor()
        now = time.time()

        # Generar embedding (si esta disponible y se solicita)
        embedding_blob = None
        if with_embedding:
            try:
                from memory.embeddings import get_embedding
                vec = get_embedding(fact)
                if vec:
                    import json as _json
                    embedding_blob = _json.dumps(vec).encode("utf-8")
            except Exception:
                pass

        try:
            if embedding_blob:
                cur.execute(
                    "INSERT INTO semantic (fact, category, confidence, source, "
                    "created_at, updated_at, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (fact, category, confidence, source, now, now, embedding_blob)
                )
            else:
                cur.execute(
                    "INSERT INTO semantic (fact, category, confidence, source, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (fact, category, confidence, source, now, now)
                )
            self.conn.commit()
            logger.info(f"Nuevo hecho aprendido [{category}]: {fact[:60]}...")
            return True
        except sqlite3.IntegrityError:
            # Reforzar confianza
            cur.execute(
                "UPDATE semantic SET confidence = MIN(1.0, confidence + 0.1), "
                "updated_at = ?, access_count = access_count + 1 "
                "WHERE fact = ?",
                (now, fact)
            )
            self.conn.commit()
            return True

    def query_knowledge(self, query: str, top_k: int = 3) -> list[dict]:
        """Busca hechos por relevancia semántica de términos significativos.

        Filtra palabras vacías (stop words) para evitar matches por 'que', 'es', etc.
        Normaliza acentos para búsqueda robusta.
        El score refleja cuántos términos significativos de la query aparecen en el hecho.

        ADEMAS: expande la query con sinonimos antes de buscar.
        Si pregunta por "auto", tambien busca hechos con "coche", "carro", etc.
        """
        cur = self.conn.cursor()
        import re as _re

        # Normalizar acentos para matching
        def _norm(t: str) -> str:
            return (t.replace('á','a').replace('é','e').replace('í','i')
                    .replace('ó','o').replace('ú','u').replace('ü','u')
                    .replace('¿','').replace('?','').replace('!','')
                    .replace('.','').replace(',',''))

        # ─── Expansion con sinonimos ───
        # Import lazy para evitar circular imports
        try:
            from learning.synonyms import get_synonyms
            use_synonyms = True
        except ImportError:
            use_synonyms = False

        if not query or not query.strip():
            cur.execute(
                "SELECT id, fact, category, confidence, source, created_at "
                "FROM semantic ORDER BY confidence DESC, created_at DESC LIMIT ?",
                (top_k * 3,)
            )
            results = []
            for row in cur.fetchall():
                results.append({
                    "doc_id": f"sem_{row['id']}",
                    "text": row['fact'],
                    "metadata": {
                        "category": row['category'],
                        "type": "semantic",
                        "confidence": row['confidence'],
                        "source": row['source'],
                    },
                    "score": row['confidence'],
                })
            return results[:top_k]

        # Stop words: palabras tan comunes que no aportan significado
        stop_words = {
            'que', 'qué', 'es', 'son', 'las', 'los', 'una', 'uno', 'unas',
            'por', 'para', 'con', 'del', 'sus', 'le', 'como', 'cómo',
            'esta', 'este', 'entre', 'todo', 'tiene', 'cada', 'sin',
            'mas', 'más', 'pero', 'era', 'han', 'has', 'sea', 'fue',
            'ello', 'ante', 'tras', 'segun', 'durante', 'mediante',
            'dónde', 'donde', 'cuándo', 'cuando', 'cuál', 'cual',
        }

        # Extraer términos significativos (≥3 caracteres, sin stop words)
        all_terms = _re.findall(r'[a-záéíóúñü0-9]{3,}', query.lower())
        terms = []
        for t in all_terms:
            tn = _norm(t)
            if tn not in stop_words:
                terms.append(tn)

        # Si no quedan términos, usar todos (incluyendo stop words)
        if not terms:
            terms = [_norm(t) for t in all_terms]
        if not terms:
            return []

        # ─── Expandir con sinonimos ───
        # Cada termino se reemplaza por TODOS sus sinonimos.
        # Asi "auto" tambien busca "coche", "carro", "vehiculo".
        expanded_terms = set(terms)
        if use_synonyms:
            for term in terms[:8]:  # Limitar para no explotar
                for syn in get_synonyms(term):
                    if syn != term:
                        expanded_terms.add(syn)

        # Buscar facts que contengan al menos uno de los términos
        results = []
        seen_ids = set()

        # Enfoque simple: cargar hechos una vez, filtrar en Python
        # LIMIT 500 para evitar cargar TODA la BD en cada query
        cur.execute(
            "SELECT id, fact, category, confidence, source, created_at, "
            "access_count "
            "FROM semantic ORDER BY confidence DESC LIMIT 500"
        )
        all_rows = cur.fetchall()

        for row in all_rows:
            fact_lower = _norm(row['fact'].lower())
            # Match con terminos ORIGINALES (mayor peso)
            original_matches = sum(1 for t in terms if t in fact_lower)
            # Match con sinonimos (menor peso)
            syn_matches = sum(
                1 for t in expanded_terms
                if t in fact_lower and t not in terms
            )
            total_matches = original_matches + (syn_matches * 0.5)

            if total_matches > 0:
                # Score base: proporcion de terminos originales matcheados
                relevance = original_matches / len(terms) if terms else 0
                # Bonus por sinonimos (sin sobrepasar 1.0)
                relevance = min(1.0, relevance + (syn_matches * 0.1))
                # Penalizar si solo matchean terminos de 3 letras comunes
                if original_matches == 1 and syn_matches == 0 and len(terms) > 2:
                    relevance *= 0.3
                results.append({
                    "doc_id": f"sem_{row['id']}",
                    "text": row['fact'],
                    "metadata": {
                        "category": row['category'],
                        "type": "semantic",
                        "confidence": row['confidence'],
                        "source": row['source'],
                    },
                    "score": round(relevance, 4),
                })

        # Ordenar por relevancia, luego por confianza
        results.sort(key=lambda x: (x['score'], x['metadata']['confidence']), reverse=True)

        # ── FASE 3: Busqueda por embeddings (complementa TF-IDF) ──
        # Solo usar embeddings si:
        # 1. TF-IDF encontro pocos resultados (< 2)
        # 2. Los resultados tienen score bajo (< 0.3)
        # Esto evita queries lentas a Ollama en cada pregunta.
        try:
            from memory.embeddings import get_embedding, cosine_similarity, is_available

            # Solo usar embeddings si TF-IDF fue debil
            tfidf_weak = (
                not results or
                all(r.get("score", 0) < 0.3 for r in results)
            )
            if not tfidf_weak:
                return results[:top_k]

            if not is_available():
                return results[:top_k]

            query_vec = get_embedding(query)
            if not query_vec:
                return results[:top_k]

            import json as _json
            # Cargar SOLO los hechos que tienen embedding (top N por confianza)
            cur.execute(
                "SELECT id, fact, category, confidence, source, embedding "
                "FROM semantic WHERE embedding IS NOT NULL "
                "ORDER BY confidence DESC LIMIT 100"
            )
            emb_rows = cur.fetchall()

            # Calcular similitud coseno para cada uno
            emb_results = []
            for row in emb_rows:
                try:
                    vec = _json.loads(row['embedding'].decode("utf-8"))
                    sim = cosine_similarity(query_vec, vec)
                    if sim > 0.4:  # Umbral minimo de similitud
                        emb_results.append({
                            "id": row['id'],
                            "text": row['fact'],
                            "sim": sim,
                            "category": row['category'],
                            "confidence": row['confidence'],
                            "source": row['source'],
                        })
                except Exception:
                    continue

            # Ordenar por similitud
            emb_results.sort(key=lambda x: x['sim'], reverse=True)

            # Si TF-IDF no encontro nada, devolver embedding results
            if not results and emb_results:
                for r in emb_results[:top_k]:
                    results.append({
                        "doc_id": f"sem_{r['id']}",
                        "text": r['text'],
                        "metadata": {
                            "category": r['category'],
                            "type": "semantic",
                            "confidence": r['confidence'],
                            "source": r['source'],
                        },
                        "score": round(r['sim'], 4),
                    })
            # Si TF-IDF encontro algo pero debil, agregar embedding results
            elif emb_results:
                existing_texts = {r['text'] for r in results}
                for r in emb_results[:top_k]:
                    if r['text'] not in existing_texts:
                        results.append({
                            "doc_id": f"sem_{r['id']}",
                            "text": r['text'],
                            "metadata": {
                                "category": r['category'],
                                "type": "semantic",
                                "confidence": r['confidence'],
                                "source": r['source'],
                            },
                            "score": round(r['sim'] * 0.9, 4),
                        })
                        existing_texts.add(r['text'])

            # Re-ordenar despues de combinar
            results.sort(key=lambda x: x['score'], reverse=True)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Error en busqueda por embeddings: {e}")

        return results[:top_k]

    def get_facts_by_category(self, category: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT fact, confidence, source, created_at FROM semantic "
            "WHERE category = ? ORDER BY confidence DESC LIMIT 100",
            (category,)
        )
        return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM semantic")
        return cur.fetchone()[0]

    def close(self):
        # conn compartida con NexusMemory — cerrar alli
        pass
