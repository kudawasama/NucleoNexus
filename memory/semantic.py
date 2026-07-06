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


class ContradictionError(Exception):
    """Excepción lanzada cuando un hecho contradice otro con confianza alta (> 0.8)."""
    def __init__(self, existing_fact: str, confidence: float):
        self.existing_fact = existing_fact
        self.confidence = confidence
        super().__init__(f"Contradice el hecho existente: '{existing_fact}' (confianza: {confidence})")


class SemanticMemory:
    """Memoria semántica — hechos y conceptos con confianza."""

    def __init__(self, db_path: str):
        import threading
        self.db_path = db_path
        # Aumentar timeout para evitar bloqueos por concurrencia
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        
        # Registrar la función personalizada de coseno en SQLite
        self.conn.create_function("cosine_sim", 2, self._sqlite_cosine_similarity)
        
        # Crear tabla si no existe e inicializar migración
        self._init_table()
        self._migrate_embeddings_format()
        
        # Iniciar worker asíncrono para embeddings
        self.worker_running = True
        self.worker_thread = threading.Thread(target=self._embedding_worker, daemon=True)
        self.worker_thread.start()

    def _sqlite_cosine_similarity(self, a_blob: bytes, b_blob: bytes) -> float:
        """Calcula la similitud coseno directamente para SQLite."""
        if not a_blob or not b_blob:
            return 0.0
        try:
            from memory.embeddings import blob_to_embed, cosine_similarity
            a = blob_to_embed(a_blob)
            b = blob_to_embed(b_blob)
            return cosine_similarity(a, b)
        except Exception:
            return 0.0

    def _migrate_embeddings_format(self):
        """Migra automáticamente embeddings en formato JSON string a BLOB binario float32."""
        with self.lock:
            cur = self.conn.cursor()
            # Verificar si la tabla existe antes de migrar
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='semantic'")
            if not cur.fetchone():
                return
            
            cur.execute("SELECT id, embedding FROM semantic WHERE embedding IS NOT NULL")
            rows = cur.fetchall()
            migrated_count = 0
            
            from memory.embeddings import blob_to_embed, embed_to_blob
            for row in rows:
                row_id = row['id']
                blob_val = row['embedding']
                # Si comienza con b'[' es formato JSON antiguo
                if blob_val and blob_val.startswith(b'['):
                    try:
                        vector = blob_to_embed(blob_val)
                        if vector:
                            binary_blob = embed_to_blob(vector)
                            cur.execute(
                                "UPDATE semantic SET embedding = ? WHERE id = ?",
                                (sqlite3.Binary(binary_blob), row_id)
                            )
                            migrated_count += 1
                    except Exception as e:
                        logger.warning(f"Error al migrar embedding ID {row_id} a binario: {e}")
            
            if migrated_count > 0:
                self.conn.commit()
                logger.info(f"Se migraron {migrated_count} embeddings a formato binario float32")

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
                        from memory.embeddings import blob_to_embed, embed_to_blob, cosine_similarity
                        try:
                            from config import THRESHOLDS
                            dedup_threshold = THRESHOLDS.get("semantic_deduplication", 0.88)
                            reinforce_inc = THRESHOLDS.get("reinforce_increment", 0.1)
                        except Exception:
                            dedup_threshold = 0.88
                            reinforce_inc = 0.1

                        for ext_row in existing_rows:
                            try:
                                ext_vec = blob_to_embed(ext_row['embedding'])
                                if not ext_vec:
                                    continue
                                sim = cosine_similarity(vec, ext_vec)
                                if sim >= dedup_threshold:  # Umbral de similitud semántica configurado
                                    ext_id = ext_row['id']
                                    ext_fact = ext_row['fact']
                                    ext_conf = ext_row['confidence']
                                    ext_access = ext_row['access_count'] or 0
                                    
                                    # Consolidar en el hecho existente
                                    new_conf = min(1.0, ext_conf + reinforce_inc)
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
                            # Proceder con la actualización normal de vector binario
                            binary_blob = embed_to_blob(vec)
                            cur.execute(
                                "UPDATE semantic SET embedding = ? WHERE id = ?",
                                (sqlite3.Binary(binary_blob), fact_id)
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
                   with_embedding: bool = True, force: bool = False) -> bool:
        """Aprende un hecho. Si ya existe, refuerza confianza.

        Con la optimizacion asincrona, el embedding se calcula en segundo plano
        por el worker si `with_embedding` es True (dejándolo inicialmente en NULL).
        """
        # 1. Verificar contradicción si no se fuerza
        if not force:
            contradiction = self.check_contradiction(fact)
            if contradiction:
                raise ContradictionError(contradiction["fact"], contradiction["confidence"])

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
                # Reforzar confianza según la configuración
                try:
                    from config import THRESHOLDS
                    reinforce_inc = THRESHOLDS.get("reinforce_increment", 0.1)
                except Exception:
                    reinforce_inc = 0.1
                cur.execute(
                    f"UPDATE semantic SET confidence = MIN(1.0, confidence + ?), "
                    "updated_at = ?, access_count = access_count + 1 "
                    "WHERE fact = ?",
                    (reinforce_inc, now, fact)
                )
                self.conn.commit()
                return True

    def check_contradiction(self, fact: str) -> dict | None:
        """Compara un hecho nuevo con hechos existentes para detectar contradicciones semánticas directas.

        Devuelve un diccionario con el hecho contradictorio y su confianza si se detecta alguno,
        o None si no hay contradicciones.
        """
        try:
            # Buscar hechos con similitud semántica en la BD usando la búsqueda híbrida actual
            existing = self.query_knowledge(fact, top_k=5)
        except Exception:
            return None

        # Normalizar y tokenizar el nuevo hecho
        w1 = set(fact.lower().replace(".", "").replace(",", "").split())
        stop_words = {
            'el', 'la', 'los', 'las', 'un', 'una', 'y', 'de', 'del', 'al', 'con', 'en', 'para', 'por', 'a',
            'es', 'son', 'esta', 'este', 'se', 'lo', 'le', 'sus'
        }
        sig1 = w1 - stop_words

        for item in existing:
            # Solo verificar contradicciones con hechos que tengan confianza alta (> 0.8)
            conf = item["metadata"].get("confidence", 0.0)
            if conf <= 0.8:
                continue

            existing_fact = item["text"]
            w2 = set(existing_fact.lower().replace(".", "").replace(",", "").split())
            sig2 = w2 - stop_words

            # Tienen que hablar del mismo tema (al menos una palabra significativa común)
            common = sig1 & sig2
            if not common:
                continue

            # 1. Contradicción por negación (ej: "X es Y" vs "X no es Y")
            has_no1 = "no" in w1
            has_no2 = "no" in w2
            if has_no1 != has_no2:
                other_words1 = sig1 - {"no"}
                other_words2 = sig2 - {"no"}
                if other_words1 and other_words2:
                    overlap = len(other_words1 & other_words2) / max(len(other_words1), len(other_words2))
                    if overlap >= 0.6:  # Solapamiento semántico alto
                        return {"fact": existing_fact, "confidence": conf}

            # 2. Contradicción por antónimos directos
            antonimos = [
                ("caliente", "frio"), ("caliente", "frío"),
                ("rapido", "lento"), ("rápido", "lento"),
                ("bueno", "malo"),
                ("alto", "bajo"),
                ("grande", "pequeño"), ("grande", "pequeno"),
                ("facil", "dificil"), ("fácil", "difícil"),
                ("abierto", "cerrado"),
                ("verdadero", "falso"),
                ("positivo", "negativo"),
                ("activo", "inactivo"),
                ("seguro", "inseguro"),
                ("correcto", "incorrecto"),
                ("valido", "invalido"), ("válido", "inválido"),
                ("fuerte", "debil"), ("fuerte", "débil"),
                ("luz", "oscuridad"), ("luz", "sombra")
            ]
            for a, b in antonimos:
                if (a in w1 and b in w2) or (b in w1 and a in w2):
                    other1 = sig1 - {a, b}
                    other2 = sig2 - {a, b}
                    if other1 and other2:
                        overlap = len(other1 & other2) / max(len(other1), len(other2))
                        if overlap >= 0.5:
                            return {"fact": existing_fact, "confidence": conf}

        return None

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

        # ─── BÚSQUEDA HÍBRIDA ───
        # 1. Búsqueda vectorial primaria si Ollama/embeddings están disponibles
        vector_results = {}
        use_vectors = False
        try:
            from memory.embeddings import get_embedding, is_available, embed_to_blob
            if is_available():
                query_vec = get_embedding(query)
                if query_vec:
                    use_vectors = True
                    query_blob = embed_to_blob(query_vec)
                    with self.lock:
                        cur = self.conn.cursor()
                        # Buscar utilizando la función de similitud coseno registrada en SQLite
                        cur.execute(
                            "SELECT id, fact, category, confidence, source, created_at, updated_at, access_count, "
                            "cosine_sim(embedding, ?) as similarity "
                            "FROM semantic WHERE embedding IS NOT NULL "
                            "ORDER BY similarity DESC LIMIT 100",
                            (sqlite3.Binary(query_blob),)
                        )
                        rows = cur.fetchall()
                    
                    try:
                        from config import THRESHOLDS
                        min_match = THRESHOLDS.get("embedding_min_match", 0.50)
                    except Exception:
                        min_match = 0.50

                    for row in rows:
                        sim = row['similarity']
                        # Considerar similitud coseno relevante según configuración
                        if sim >= min_match:
                            updated_at = row['updated_at'] or row['created_at'] or now
                            delta_days = (now - updated_at) / 86400.0
                            time_decay = max(0.2, decay_rate ** delta_days)
                            access_count = row['access_count'] or 0
                            access_factor = 1.0 + 0.1 * math.log(access_count + 1)
                            score_vec = sim * time_decay * access_factor
                            
                            vector_results[row['fact']] = {
                                "id": row['id'],
                                "category": row['category'],
                                "confidence": row['confidence'],
                                "source": row['source'],
                                "score_vec": score_vec
                            }
        except Exception as e:
            logger.debug(f"Error en búsqueda por embeddings primaria: {e}")

        # 2. Búsqueda TF-IDF (con stopwords y sinónimos)
        tfidf_results = {}
        with self.lock:
            cur = self.conn.cursor()
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
                
                updated_at = row['updated_at'] or row['created_at'] or now
                delta_days = (now - updated_at) / 86400.0
                time_decay = max(0.2, decay_rate ** delta_days)
                access_count = row['access_count'] or 0
                access_factor = 1.0 + 0.1 * math.log(access_count + 1)
                
                score_tfidf = relevance * time_decay * access_factor
                tfidf_results[row['fact']] = {
                    "id": row['id'],
                    "category": row['category'],
                    "confidence": row['confidence'],
                    "source": row['source'],
                    "score_tfidf": score_tfidf
                }

        # 3. Combinación Híbrida de Scores
        results = []
        all_facts = set(vector_results.keys()) | set(tfidf_results.keys())

        for fact in all_facts:
            v_data = vector_results.get(fact)
            t_data = tfidf_results.get(fact)
            
            # Obtener datos comunes
            item_data = v_data or t_data
            
            # Ponderación del Score Híbrido: 60% Vectorial, 40% TF-IDF
            score_final = 0.0
            if v_data and t_data:
                # Si aparece en ambos, sumamos ponderados (con un boost por coincidencia híbrida)
                score_final = (0.6 * v_data["score_vec"]) + (0.4 * t_data["score_tfidf"])
            elif v_data:
                score_final = 0.6 * v_data["score_vec"]
            elif t_data:
                # Si solo está en TF-IDF y usamos vectores, penalizamos ligeramente la ausencia semántica
                weight = 0.4 if use_vectors else 1.0
                score_final = weight * t_data["score_tfidf"]
                
            results.append({
                "doc_id": f"sem_{item_data['id']}",
                "id_int": item_data['id'],
                "text": fact,
                "metadata": {
                    "category": item_data['category'],
                    "type": "semantic",
                    "confidence": item_data['confidence'],
                    "source": item_data['source'],
                },
                "score": round(score_final, 4),
            })

        results.sort(key=lambda x: x['score'], reverse=True)

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
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT fact, confidence, source, created_at FROM semantic "
                "WHERE category = ? ORDER BY confidence DESC LIMIT 100",
                (category,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_consolidable_facts(self, min_confidence: float = None) -> list[dict]:
        """Devuelve hechos aprendidos en runtime listos para consolidar a JSON.

        Solo incluye hechos con confidence >= min_confidence cuyo source
        NO sea 'knowledge_base' (esos ya están en los JSON de origen).
        """
        if min_confidence is None:
            try:
                from config import THRESHOLDS
                min_confidence = THRESHOLDS.get("consolidation_min_conf", 0.8)
            except Exception:
                min_confidence = 0.8

        with self.lock:
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
        with self.lock:
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
