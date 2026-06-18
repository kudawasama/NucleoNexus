#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta: Renombrador Inteligente de PDFs
=============================================
Lee facturas PDF, extrae proveedor y fecha del contenido,
y renombra los archivos con el formato:

    {numero} - {PROVEEDOR_CORTO} - {MES AÑO}.pdf

Uso:
    python tools/pdf_renamer.py "C:/ruta/a/pdf/o/archivo.zip"
    python tools/pdf_renamer.py "C:/ruta/carpeta" --dry-run
    python tools/pdf_renamer.py "C:/ruta/carpeta" --add-provider "NuevoProveedor SpA=NUEVOPROV"
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# ── MAPEO DE PROVEEDORES ─────────────────────────────────────────────
# Formato: "Razon Social Exacta": "NOMBRE_CORTO"
# Agregar nuevos proveedores aquí o via --add-provider
PROVIDER_MAP = {
    "Megacentro Carrascal SpA": "MEGACARRASCAL",
    "Centro Logístico y Distribución Megacentro - Enea SpA": "MEGAENEA",
    "Rentas Buenaventura SpA": "MEGABUENAV",
    "Rentas Miraflores SpA": "MEGAMIRAFLOR",
    "Rentco SpA": "RENTCO",
}

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

# ── CONFIG PERSISTENTE ───────────────────────────────────────────────
CONFIG_DIR = Path(__file__).parent.parent / "data" / "tools"
CONFIG_FILE = CONFIG_DIR / "pdf_renamer_providers.json"


def _load_providers():
    """Carga mapeo de proveedores, combinando el built-in + persisted."""
    providers = dict(PROVIDER_MAP)
    if CONFIG_FILE.exists():
        try:
            extra = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            providers.update(extra)
        except (json.JSONDecodeError, OSError):
            pass
    return providers


def _save_providers(providers: dict):
    """Persiste mapeo extra de proveedores (no toca los built-in)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Solo guardar los que NO son built-in
    extra = {k: v for k, v in providers.items() if k not in PROVIDER_MAP}
    CONFIG_FILE.write_text(
        json.dumps(extra, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── EXTRACCION DESDE PDF ─────────────────────────────────────────────


def _extraer_de_pdf(path: str) -> dict | None:
    """Abre un PDF con pymupdf y extrae: razon_social, numero, fecha."""
    try:
        import pymupdf
    except ImportError:
        print("ERROR: Se necesita pymupdf. Instala con: pip install pymupdf")
        sys.exit(1)

    try:
        doc = pymupdf.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception as e:
        print(f"  ⚠ Error leyendo {Path(path).name}: {e}")
        return None

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return None

    razon_social = lines[0]  # Primera línea = nombre del proveedor

    # Número de factura
    m_num = re.search(r"N°(\d+)", text)
    if not m_num:
        return None
    numero = m_num.group(1)

    # Fecha de emisión: dd-mm-yyyy
    m_fecha = re.search(r"Fecha Emisión\s*:\s*(\d{2})-(\d{2})-(\d{4})", text)
    if not m_fecha:
        return None
    dia, mes, anio = int(m_fecha.group(1)), int(m_fecha.group(2)), int(m_fecha.group(3))
    mes_nombre = MESES.get(mes, f"MES{mes}")

    return {
        "razon_social": razon_social,
        "numero": numero,
        "anio": anio,
        "mes": mes_nombre,
    }


# ── PROCESAMIENTO ────────────────────────────────────────────────────


def _encontrar_pdfs(origen: str) -> list[tuple[str, str]]:
    """
    Dado un path (carpeta o ZIP), retorna lista de (ruta_completa, nombre_archivo).
    Si es ZIP, extrae a temp y trabaja desde ahí.
    """
    path = Path(origen)
    if not path.exists():
        print(f"ERROR: No existe: {origen}")
        sys.exit(1)

    # ── ZIP ──
    if path.suffix.lower() == ".zip":
        temp_dir = Path(tempfile.mkdtemp(prefix="pdf_renamer_"))
        print(f"  📦 Extrayendo ZIP a {temp_dir}...")
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(temp_dir)
        # Buscar PDFs dentro (pueden estar en subcarpetas)
        pdfs = []
        for fpath in sorted(temp_dir.rglob("*.pdf")):
            pdfs.append((str(fpath), fpath.name))
        if not pdfs:
            print("ERROR: No se encontraron PDFs dentro del ZIP.")
            shutil.rmtree(temp_dir)
            sys.exit(1)
        return pdfs, temp_dir

    # ── CARPETA ──
    if path.is_dir():
        pdfs = []
        for f in sorted(path.iterdir()):
            if f.suffix.lower() == ".pdf" and f.is_file():
                pdfs.append((str(f), f.name))
        if not pdfs:
            print(f"ERROR: No hay PDFs en: {origen}")
            sys.exit(1)
        return pdfs, None

    # ── PDF individual ──
    if path.suffix.lower() == ".pdf":
        return [(str(path), path.name)], None

    print(f"ERROR: No es PDF, carpeta ni ZIP: {origen}")
    sys.exit(1)


def procesar(origen: str, dry_run: bool = False, proveedores: dict | None = None):
    """Ejecuta el renombrado."""
    if proveedores is None:
        proveedores = _load_providers()

    pdfs, temp_dir = _encontrar_pdfs(origen)
    destino_base = Path(origen)
    using_temp = temp_dir is not None

    # Si viene de ZIP, el destino es una carpeta nueva al lado del ZIP
    if using_temp:
        destino_base = Path(origen).parent / f"{Path(origen).stem}_renombrados"
        destino_base.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*65}")
    print(f"  RENOMBRADOR DE PDFS — {'SIMULACION' if dry_run else 'EJECUTANDO'}")
    print(f"{'='*65}")
    print(f"  Origen: {origen}")
    print(f"  {'Destino: ' + str(destino_base) if using_temp else ''}")
    print(f"{'='*65}\n")

    resultados = []
    errores = []
    no_match = []

    for fullpath, fname in pdfs:
        data = _extraer_de_pdf(fullpath)
        if data is None:
            errores.append(fname)
            continue

        rs = data["razon_social"]
        corto = proveedores.get(rs)
        if corto is None:
            no_match.append((fname, rs))
            continue

        new_name = f"{data['numero']} - {corto} - {data['mes']} {data['anio']}.pdf"
        resultados.append((fname, new_name))

    # ── Reporte ──
    for old, new in resultados:
        print(f"  {old:50s} → {new}")

    for old, rs in no_match:
        print(f"  ⚠ {old:50s} → PROVEEDOR NO RECONOCIDO: {rs}")

    for old in errores:
        print(f"  ✗ {old:50s} → ERROR al leer PDF")

    # ── Ejecutar renombre ──
    if not dry_run and resultados:
        ok = 0
        for old, new in resultados:
            old_path = Path(pdfs[resultados.index((old, new))][0])
            if using_temp:
                # Copiar con nuevo nombre al destino
                shutil.copy2(str(old_path), str(destino_base / new))
                ok += 1
            else:
                new_path = old_path.parent / new
                if new_path.exists():
                    print(f"  ✗ YA EXISTE: {new}")
                    continue
                old_path.rename(new_path)
                ok += 1
        print(f"\n  ✅ {ok} archivos renombrados.")

        if no_match:
            print(f"\n  ⚠ {len(no_match)} archivos con proveedor no mapeado.")
            print("     Para agregarlos usa: --add-provider \"Razon Social=NOMBRE\"")
    elif dry_run:
        print(f"\n  📋 Simulación — no se modificó ningún archivo.")

    if errores:
        print(f"\n  ✗ {len(errores)} archivos no se pudieron leer.")

    # Limpiar temp si venía de ZIP
    if using_temp and temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return len(resultados), len(errores), len(no_match)


# ── CLI ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Renombrador inteligente de PDFs de facturas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s "C:/Users/jose/Downloads/Facturas/"
  %(prog)s "C:/Users/jose/Downloads/Facturas.zip" --dry-run
  %(prog)s "C:/Users/jose/Downloads/" --add-provider "Nueva Empresa SpA=NUEVAEMP"
        """,
    )
    parser.add_argument("origen", nargs="?", default=None, help="Carpeta con PDFs, ZIP, o PDF individual")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar cambios, no renombrar")
    parser.add_argument("--add-provider", metavar='"Razon Social=NOMBRE"',
                        help="Agregar un nuevo mapeo de proveedor (ej: 'MiEmpresa SpA=MIEMP')")
    parser.add_argument("--list-providers", action="store_true", help="Listar proveedores conocidos")

    args = parser.parse_args()

    if args.list_providers:
        provs = _load_providers()
        print("\nProveedores conocidos:")
        for rs, corto in sorted(provs.items()):
            print(f"  {corto:20s} ← {rs}")
        return

    if args.add_provider:
        if "=" not in args.add_provider:
            print("ERROR: Formato debe ser: \"Razon Social=NOMBRE_CORTO\"")
            sys.exit(1)
        rs, corto = args.add_provider.split("=", 1)
        rs, corto = rs.strip(), corto.strip()
        provs = _load_providers()
        provs[rs] = corto
        _save_providers(provs)
        print(f"  ✅ Proveedor agregado: {corto} ← {rs}")
        return

    if not args.origen:
        parser.print_help()
        sys.exit(1)

    procesar(args.origen, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
