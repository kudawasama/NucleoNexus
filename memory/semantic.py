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
        import threading
        self.db_path = db_path
        # Aumentar timeout para evitar bloqueos por concurrencia
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        
        # Iniciar worker asíncrono para embeddings
        self.worker_running = True
        self.worker_thread = threading.Thread(target=self._embedding_worker, daemon=True)
        self.worker_thread.start()

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

    def _embedding_worker(self):
        """Worker en segundo plano para procesar embeddings pendientes."""
        import time
        import json as _json
        import sqlite3
        
        # Conexión propia del hilo secundario
        worker_conn = None
        failed_attempts = {}  # fact_id -> intentos fallidos
        
        while self.worker_running:
            try:
                # Comprobar si el modelo de embeddings está disponible
                from memory.embeddings import get_embedding, is_available
                if not is_available():
                    time.sleep(10)
                    continue

                if not worker_conn:
                    worker_conn = sqlite3.connect(self.db_path, timeout=10.0)
                    worker_conn.row_factory = sqlite3.Row

                cur = worker_conn.cursor()
                
                # Excluir hechos que fallan continuamente para evitar bucles infinitos
                exclude_ids = [fid for fid, att in failed_attempts.items() if att >= 3]
                if exclude_ids:
                    placeholders = ",".join("?" for _ in exclude_ids)
                    query = f"SELECT id, fact FROM semantic WHERE embedding IS NULL AND id NOT IN ({placeholders}) LIMIT 5"
                    cur.execute(query, tuple(exclude_ids))
                else:
                    cur.execute("SELECT id, fact FROM semantic WHERE embedding IS NULL LIMIT 5")
                
                rows = cur.fetchall()

                if not rows:
                    time.sleep(3)
                    continue

                for row in rows:
                    if not self.worker_running:
                        break
                    fact_id = row['id']
                    fact_text = row['fact']
                    
                    logger.debug(f"Worker generando embedding para hecho #{fact_id}...")
                    vec = get_embedding(fact_text)
                    if vec:
                        # Buscar hechos similares existentes en la base de datos (con embedding calculado y diferente id)
                        cur.execute(
                            "SELECT id, fact, confidence, access_count, embedding "
                            "FROM semantic WHERE embedding IS NOT NULL AND id != ?",
                            (fact_id,)
                        )
                        existing_rows = cur.fetchall()
                        
                        duplicate_found = False
                        for ext_row in existing_rows:
                            try:
                                ext_vec = _json.loads(ext_row['embedding'].decode("utf-8"))
                                from memory.embeddings import cosine_similarity
                                sim = cosine_similarity(vec, ext_vec)
                                if sim >= 0.88:  # Umbral de similitud semántica
                                    ext_id = ext_row['id']
                                    ext_fact = ext_row['fact']
                                    ext_conf = ext_row['confidence']
                                    ext_access = ext_row['access_count'] or 0
                                    
                                    # Consolidar en el hecho existente
                                    new_conf = min(1.0, ext_conf + 0.1)
                                    new_access = ext_access + 1
                                    
                                    cur.execute(
                                        "UPDATE semantic SET confidence = ?, access_count = ?, updated_at = ? WHERE id = ?",
                                        (new_conf, new_access, time.time(), ext_id)
                                    )
                                    # Eliminar el nuevo hecho duplicado redundante
                                    cur.execute("DELETE FROM semantic WHERE id = ?", (fact_id,))
                                    worker_conn.commit()
                                    
                                    logger.info(
                                        f"Consolidación semántica: '{fact_text[:40]}' fusionado en "
                                        f"'{ext_fact[:40]}' (similitud: {sim:.2f})"
                                    )
                                    duplicate_found = True
                                    break
                            except Exception as ex:
                                logger.debug(f"Error procesando similitud en consolidación: {ex}")
                                continue
                        
                        if not duplicate_found:
                            # Proceder con la actualización normal de vector
                            blob = _json.dumps(vec).encode("utf-8")
                            cur.execute(
                                "UPDATE semantic SET embedding = ? WHERE id = ?",
                                (blob, fact_id)
                            )
                            worker_conn.commit()
                            logger.info(f"Worker guardó embedding para hecho #{fact_id}")
                            
                        if fact_id in failed_attempts:
                            del failed_attempts[fact_id]
                    else:
                        failed_attempts[fact_id] = failed_attempts.get(fact_id, 0) + 1
                        logger.warning(
                            f"Worker no pudo generar embedding para hecho #{fact_id}. "
                            f"Intento: {failed_attempts[fact_id]}/3"
                        )
                        time.sleep(1)
                
            except sqlite3.OperationalError as oe:
                logger.debug(f"Worker de embeddings: base de datos bloqueada ({oe}). Reintentando...")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Error en worker de embeddings: {e}")
                time.sleep(5)
        
        if worker_conn:
            try:
                worker_conn.close()
            except Exception:
                pass

    def learn_fact(self, fact: str, category: str = "general",
                   confidence: float = 0.5, source: str = None,
                   with_embedding: bool = True) -> bool:
        """Aprende un hecho. Si ya existe, refuerza confianza.

        Con la optimizacion asincrona, el embedding se calcula en segundo plano
        por el worker si `with_embedding` es True (dejándolo inicialmente en NULL).
        """
        with self.lock:
            cur = self.conn.cursor()
            now = time.time()

            try:
                # Insertamos con embedding = NULL. El worker de fondo lo procesará
                cur.execute(
                    "INSERT INTO semantic (fact, category, confidence, source, "
                    "created_at, updated_at, embedding) VALUES (?, ?, ?, ?, ?, ?, NULL)",
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
        El score refleja la relevancia semántica modificada por un factor de decaimiento
        temporal y de frecuencia de acceso para favorecer hechos recientes y útiles.

        ADEMAS: expande la query con sinonimos antes de buscar.
        """
        import math
        now = time.time()
        
        # Cargar decay_rate desde la config
        try:
            from config import MEMORY
            decay_rate = MEMORY.get("decay_rate", 0.99)
        except Exception:
            decay_rate = 0.99

        # Normalizar acentos para matching
        def _norm(t: str) -> str:
            return (t.replace('á','a').replace('é','e').replace('í','i')
                    .replace('ó','o').replace('ú','u').replace('ü','u')
                    .replace('¿','').replace('?','').replace('!','')
                    .replace('.','').replace(',',''))

        # ─── Expansion con sinonimos ───
        try:
            from learning.synonyms import get_synonyms
            use_synonyms = True
        except ImportError:
            use_synonyms = False

        with self.lock:
            cur = self.conn.cursor()
            if not query or not query.strip():
                cur.execute(
                    "SELECT id, fact, category, confidence, source, created_at, updated_at, access_count "
                    "FROM semantic ORDER BY confidence DESC, created_at DESC LIMIT ?",
                    (top_k * 3,)
                )
                results = []
                for row in cur.fetchall():
                    # Decaimiento temporal
                    updated_at = row['updated_at'] or row['created_at'] or now
                    delta_days = (now - updated_at) / 86400.0
                    time_decay = max(0.2, decay_rate ** delta_days)
                    
                    # Frecuencia de acceso
                    access_count = row['access_count'] or 0
                    access_factor = 1.0 + 0.1 * math.log(access_count + 1)
                    
                    score_final = row['confidence'] * time_decay * access_factor
                    
                    results.append({
                        "doc_id": f"sem_{row['id']}",
                        "id_int": row['id'],
                        "text": row['fact'],
                        "metadata": {
                            "category": row['category'],
                            "type": "semantic",
                            "confidence": row['confidence'],
                            "source": row['source'],
                        },
                        "score": round(score_final, 4),
                    })
                
                # Incrementar accesos para los retornados
                selected_ids = [r["id_int"] for r in results[:top_k] if r.get("id_int")]
                if selected_ids:
                    try:
                        placeholders = ",".join("?" for _ in selected_ids)
                        cur.execute(
                            f"UPDATE semantic SET access_count = access_count + 1, updated_at = ? WHERE id IN ({placeholders})",
                            (now, *selected_ids)
                        )
                        self.conn.commit()
                    except Exception as e:
                        logger.debug(f"Error al actualizar access_count: {e}")
                        
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
        import re as _re
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
        expanded_terms = set(terms)
        if use_synonyms:
            for term in terms[:8]:  # Limitar para no explotar
                for syn in get_synonyms(term):
                    if syn != term:
                        expanded_terms.add(syn)

        # Buscar facts que contengan al menos uno de los términos
        results = []

        with self.lock:
            cur = self.conn.cursor()
            # LIMIT 500 para evitar cargar toda la BD
            cur.execute(
                "SELECT id, fact, category, confidence, source, created_at, updated_at, access_count "
                "FROM semantic ORDER BY confidence DESC LIMIT 500"
            )
            all_rows = cur.fetchall()

        for row in all_rows:
            fact_lower = _norm(row['fact'].lower())
            original_matches = sum(1 for t in terms if t in fact_lower)
            syn_matches = sum(
                1 for t in expanded_terms
                if t in fact_lower and t not in terms
            )
            total_matches = original_matches + (syn_matches * 0.5)

            if total_matches > 0:
                relevance = original_matches / len(terms) if terms else 0
                relevance = min(1.0, relevance + (syn_matches * 0.1))
                if original_matches == 1 and syn_matches == 0 and len(terms) > 2:
                    relevance *= 0.3
                
                # Calcular decaimiento temporal y factor de accesos
                updated_at = row['updated_at'] or row['created_at'] or now
                delta_days = (now - updated_at) / 86400.0
                time_decay = max(0.2, decay_rate ** delta_days)
                
                access_count = row['access_count'] or 0
                access_factor = 1.0 + 0.1 * math.log(access_count + 1)
                
                score_final = relevance * time_decay * access_factor
                
                results.append({
                    "doc_id": f"sem_{row['id']}",
                    "id_int": row['id'],
                    "text": row['fact'],
                    "metadata": {
                        "category": row['category'],
                        "type": "semantic",
                        "confidence": row['confidence'],
                        "source": row['source'],
                    },
                    "score": round(score_final, 4),
                })

        # Ordenar por relevancia modificada
        results.sort(key=lambda x: x['score'], reverse=True)

        # ── FASE 3: Busqueda por embeddings (complementa TF-IDF) ──
        try:
            from memory.embeddings import get_embedding, cosine_similarity, is_available

            # Solo usar embeddings si TF-IDF fue debil
            tfidf_weak = (
                not results or
                all(r.get("score", 0) < 0.3 for r in results)
            )
            
            if tfidf_weak and is_available():
                query_vec = get_embedding(query)
                if query_vec:
                    with self.lock:
                        cur = self.conn.cursor()
                        cur.execute(
                            "SELECT id, fact, category, confidence, source, created_at, updated_at, access_count, embedding "
                            "FROM semantic WHERE embedding IS NOT NULL "
                            "ORDER BY confidence DESC LIMIT 100"
                        )
                        emb_rows = cur.fetchall()

                    import json as _json
                    emb_results = []
                    for row in emb_rows:
                        try:
                            vec = _json.loads(row['embedding'].decode("utf-8"))
                            sim = cosine_similarity(query_vec, vec)
                            if sim > 0.55:
                                # Calcular decaimiento temporal y factor de accesos
                                updated_at = row['updated_at'] or row['created_at'] or now
                                delta_days = (now - updated_at) / 86400.0
                                time_decay = max(0.2, decay_rate ** delta_days)
                                
                                access_count = row['access_count'] or 0
                                access_factor = 1.0 + 0.1 * math.log(access_count + 1)
                                
                                adjusted_sim = sim * time_decay * access_factor
                                
                                emb_results.append({
                                    "id": row['id'],
                                    "text": row['fact'],
                                    "sim": adjusted_sim,
                                    "category": row['category'],
                                    "confidence": row['confidence'],
                                    "source": row['source'],
                                })
                        except Exception:
                            continue

                    emb_results.sort(key=lambda x: x['sim'], reverse=True)

                    if not results and emb_results:
                        for r in emb_results[:top_k]:
                            results.append({
                                "doc_id": f"sem_{r['id']}",
                                "id_int": r['id'],
                                "text": r['text'],
                                "metadata": {
                                    "category": r['category'],
                                    "type": "semantic",
                                    "confidence": r['confidence'],
                                    "source": r['source'],
                                },
                                "score": round(r['sim'], 4),
                            })
                    elif emb_results:
                        existing_texts = {r['text'] for r in results}
                        for r in emb_results[:top_k]:
                            if r['text'] not in existing_texts:
                                results.append({
                                    "doc_id": f"sem_{r['id']}",
                                    "id_int": r['id'],
                                    "text": r['text'],
                                    "metadata": {
                                        "category": r['category'],
                                        "type": "semantic",
                                        "confidence": r['confidence'],
                                        "source": r['source'],
                                        "embedding_adjusted": True,
                                    },
                                    "score": round(r['sim'] * 0.9, 4),
                                })
                                existing_texts.add(r['text'])

                    results.sort(key=lambda x: x['score'], reverse=True)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Error en busqueda por embeddings: {e}")

        # Incrementar accesos para los retornados finales
        if results:
            selected_ids = [r["id_int"] for r in results[:top_k] if r.get("id_int")]
            if selected_ids:
                try:
                    with self.lock:
                        cur = self.conn.cursor()
                        placeholders = ",".join("?" for _ in selected_ids)
                        cur.execute(
                            f"UPDATE semantic SET access_count = access_count + 1, updated_at = ? WHERE id IN ({placeholders})",
                            (now, *selected_ids)
                        )
                        self.conn.commit()
                except Exception as e:
                    logger.debug(f"Error al actualizar access_count: {e}")

        return results[:top_k]

    def get_facts_by_category(self, category: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT fact, confidence, source, created_at FROM semantic "
            "WHERE category = ? ORDER BY confidence DESC LIMIT 100",
            (category,)
        )
        return [dict(r) for r in cur.fetchall()]

    def get_consolidable_facts(self, min_confidence: float = 0.8) -> list[dict]:
        """Devuelve hechos aprendidos en runtime listos para consolidar a JSON.

        Solo incluye hechos con confidence >= min_confidence cuyo source
        NO sea 'knowledge_base' (esos ya están en los JSON de origen).
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, fact, category, confidence, source FROM semantic "
            "WHERE confidence >= ? AND source != 'knowledge_base' "
            "ORDER BY confidence DESC LIMIT 50",
            (min_confidence,)
        )
        return [dict(r) for r in cur.fetchall()]

    def mark_as_consolidated(self, fact_id: int):
        """Marca un hecho como consolidado (cambia source a 'knowledge_base')."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE semantic SET source = 'knowledge_base' WHERE id = ?",
            (fact_id,)
        )
        self.conn.commit()

    def count(self) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM semantic")
            return cur.fetchone()[0]

    def close(self):
        self.worker_running = False
