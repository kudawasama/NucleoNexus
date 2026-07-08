# 13 — Tools Auxiliares (`tools/` + `utils/`)

> **Herramientas de soporte que no son parte del flujo cognitivo principal** pero extienden capacidades.

---

## A) Renombrador Inteligente de PDFs (`tools/pdf_renamer.py`)

> *"Lee facturas PDF, extrae proveedor y fecha del contenido, y renombra los archivos con el formato:*
> **N°{numero}_{PROVEEDOR_CORTO}_{MES}_{AÑO}.pdf***
> *Incluye detección automática de conflictos: si dos proveedores comparten la misma marca (ej: ENEL Distribución / ENEL Generación), los diferencia incluyendo la palabra de giro."*

### Formato de renombrado

```
N°{numero}_{PROVEEDOR_CORTO}_{MES}_{AÑO}.pdf
```

**Ejemplo:**
```
N°12345_ENELDISTRI_JUNIO_2026.pdf
```

### Uso

```bash
# Renombrar carpeta
python tools/pdf_renamer.py "C:/ruta/carpeta"

# Renombrar con zip
python tools/pdf_renamer.py "C:/ruta/archivo.zip"

# Solo previsualizar (no renombra)
python tools/pdf_renamer.py "C:/ruta/carpeta" --dry-run
```

### Algoritmo

1. Listar archivos PDF en la ruta
2. Para cada PDF:
   a. Leer contenido (texto + tablas)
   b. Extraer: número de factura, RUT proveedor, razón social, fecha
   c. Derivar nombre corto del proveedor (ver regla abajo)
   d. Formatear fecha como "MES AÑO" (ej: "JUNIO 2026")
   e. Construir nuevo nombre: `N°{numero}_{PROVEEDOR_CORTO}_{MES}_{AÑO}.pdf`
3. Detectar conflictos: si dos archivos quedarían con el mismo nombre, agrega sufijo numérico (`_1`, `_2`)
4. Renombrar (con `--dry-run` solo muestra el cambio propuesto)

### `derive_short_name(razon_social)` — Nombre corto del proveedor

> *"Para no-Megacentro usa siempre los primeros 2 tokens significativos (marca + giro), así 'ENEL Distribución' → ENELDISTRI (no solo ENEL)."*

**Reglas:**
1. **Megacentro** → "MEGACENTRO" (sin transformación)
2. **Otros** → concatenar primeros 2 tokens significativos, max 10-12 chars en total, uppercase, sin acentos.

**Detección de conflictos** (mismo nombre corto):
- Si dos proveedores producen el mismo nombre corto → el conflicto se resuelve incluyendo la palabra de giro.
- Ejemplo: "ENEL Distribución" y "ENEL Generación" → "ENELDISTRI" y "ENELGENER".

### Estructura de retorno

```python
{
  "renamed": [...],     # archivos renombrados exitosamente
  "skipped": [...],     # archivos no procesados (sin número, sin fecha, etc)
  "errors": [...],      # errores de lectura
  "conflicts": [...],   # conflictos resueltos
}
```

---

## B) Git Automático (`utils/git_auto.py`)

> *"Commit + push + pull automático sin intervención del usuario.*
> *Se ejecuta en background después de cada interacción."*

### Constantes

```python
PUSH_INTERVAL = 30  # mínimo de segundos entre pushes
```

### `auto_commit_push(message="auto: sync")` — Sincronización silenciosa

**Algoritmo:**

1. **`git pull --rebase`** — actualiza el repo local
2. **`git add -A`** — stagea todos los cambios
3. **`git status --porcelain`** — verifica si hay cambios
4. Si no hay cambios → retorna `False` (sin hacer nada)
5. **`git commit -m message`** — commitea
6. **Throttle**: si pasaron menos de `PUSH_INTERVAL` segundos desde el último push → no hace push
7. **`git push`** — sube al remoto

**Returns:** `True` si hubo commit+push, `False` en caso contrario.

### Características

- **No falla el sistema**: errores de git se capturan con `try/except`
- **Silent mode**: no imprime nada al usuario
- **Throttle**: evita spam de pushes en interacciones rápidas
- **Timeouts**: 15s para comandos normales, 30s para push

### Cuándo se llama

- **Al iniciar Nexus** → `auto_pull()` (en `main.py:__init__`)
- **Después de cada interacción** → `auto_commit_push()` con mensaje `auto: interacción #N`

### Pitfalls documentados

- En Windows: `git: 'credential-manager-core' is not a git command` puede aparecer como warning del credential helper, pero el push igual funciona.
- Si hay conflictos de merge, `git pull --rebase` puede fallar → no se commitea nada hasta resolver manualmente.

---

## Filosofía

> Estas herramientas son **extensiones laterales** del proyecto: no son parte del núcleo cognitivo (cognición + memoria + skills), pero añaden capacidades útiles para los casos de uso reales del autor (facturas PDF chilenas) y para mantener el repo sincronizado.
