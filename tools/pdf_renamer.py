#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta: Renombrador Inteligente de PDFs
=============================================
Lee facturas PDF, extrae proveedor y fecha del contenido,
y renombra los archivos con el formato:

    {numero} - {PROVEEDOR_CORTO} - {MES AÑO}.pdf

Uso:
    python tools/pdf_renamer.py "C:/ruta/carpeta"
    python tools/pdf_renamer.py "C:/ruta/archivo.zip" --dry-run
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

# Palabras a eliminar de la razon social (sufijos legales + conectores)
_STOP = {
    "de", "del", "de la", "de las", "de los", "y", "e", "el", "la",
    "los", "las", "un", "una", "en", "al", "por", "para", "con",
}

# Sufijos legales (orden: mas especifico primero)
_SUFIJOS = [
    " SpA", " S.A.", " S.A", " SA", " Ltda", " Limitada",
    " E.I.R.L.", " EIRL",
]

# Palabras de giro generico que no aportan identidad
_GIRO = {
    "arriendo", "compra", "venta", "bienes", "inmuebles",
    "amoblados", "equipos", "maquinarias", "distribucion",
    "distribución", "logistico", "logístico", "centro",
    "comercial", "industrial", "profesional",
}


def _abreviar_proveedor(razon_social: str) -> str:
    """Deriva nombre corto (~10-12 chars) desde la razon social del PDF.

    Estrategia:
    1. Limpiar sufijos legales, conectores y palabras de giro
    2. Separar por guion si existe — la parte derecha suele ser la identidad
    3. Si la empresa pertenece al grupo Megacentro → prefijo MEGA + palabra clave
    4. Palabra clave > 8 chars → truncar a 6 (ej: Buenaventura → BUENAV)
    5. Sino → usar la(s) palabra(s) significativa(s) tal cual
    """
    nombre = razon_social.strip()

    # ── 1. Quitar sufijos legales ──
    nombre_upper = nombre.upper()
    for suf in _SUFIJOS:
        if nombre_upper.endswith(suf.upper()):
            nombre = nombre[:-len(suf)].strip()
            break

    # ── 2. Separar por guion: "X - Y" → la parte derecha es la identidad ──
    if " - " in nombre:
        partes = nombre.split(" - ")
        if len(partes) >= 2:
            nombre = partes[-1].strip()

    # ── 3. Tokenizar y filtrar ──
    # Reemplazar puntuacion por espacios
    nombre_clean = re.sub(r'[^\w\s]', ' ', nombre)
    tokens = nombre_clean.split()
    tokens = [t for t in tokens if t.lower() not in _STOP]
    tokens = [t for t in tokens if t.lower() not in _GIRO]

    if not tokens:
        tokens = [t for t in nombre_clean.split() if t.lower() not in _STOP]
    if not tokens:
        return "DESCONOCIDO"

    # ── 4. Detectar grupo Megacentro ──
    # "Megacentro Carrascal", "Centro Logístico ... Megacentro - Enea"
    # "Rentas Buenaventura", "Rentas Miraflores"
    # (Rentco es independiente, NO lleva MEGA)
    full_upper = razon_social.upper()
    es_grupo_mega = "MEGACENTRO" in full_upper
    es_rentas = full_upper.startswith("RENTAS")
    if es_grupo_mega or es_rentas:
        clave = tokens[-1].upper()  # la ultima palabra es la mas especifica
        if len(clave) > 8:
            clave = clave[:6]
        return f"MEGA{clave}"

    # ── 5. Otros proveedores: usar la palabra mas significativa ──
    if len(tokens) == 1:
        return tokens[0].upper()[:12]

    # Multipalabra: tomar ultima (suele ser la especifica) o primera si es larga
    ultima = tokens[-1].upper()
    if len(ultima) >= 5:
        return ultima[:12]
    return (tokens[0].upper()[:6] + tokens[-1].upper()[:6])[:12]


def _extraer_de_pdf(path: str) -> dict | None:
    """Abre un PDF con pymupdf y extrae: razon_social, numero, fecha."""
    try:
        import pymupdf
    except ImportError:
        print("ERROR: Se necesita pymupdf. pip install pymupdf")
        sys.exit(1)

    try:
        doc = pymupdf.open(path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception as e:
        return None

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return None

    razon_social = lines[0]

    m_num = re.search(r"N°(\d+)", text)
    if not m_num:
        return None
    numero = m_num.group(1)

    m_fecha = re.search(r"Fecha Emisión\s*:\s*(\d{2})-(\d{2})-(\d{4})", text)
    if not m_fecha:
        return None
    _, mes, anio = int(m_fecha.group(1)), int(m_fecha.group(2)), int(m_fecha.group(3))
    mes_nombre = MESES.get(mes, f"MES{mes}")

    return {
        "razon_social": razon_social,
        "numero": numero,
        "anio": anio,
        "mes": mes_nombre,
        "corto": _abreviar_proveedor(razon_social),
    }


def _encontrar_pdfs(origen: str) -> tuple[list[tuple[str, str]], Path | None]:
    """Retorna (lista (ruta_completa, nombre_archivo), temp_dir_opcional)."""
    path = Path(origen)
    if not path.exists():
        print(f"ERROR: No existe: {origen}")
        sys.exit(1)

    if path.suffix.lower() == ".zip":
        temp_dir = Path(tempfile.mkdtemp(prefix="pdf_renamer_"))
        print(f"  📦 Extrayendo ZIP...")
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(temp_dir)
        pdfs = [(str(f), f.name) for f in sorted(temp_dir.rglob("*.pdf"))]
        if not pdfs:
            print("ERROR: No hay PDFs en el ZIP.")
            shutil.rmtree(temp_dir)
            sys.exit(1)
        return pdfs, temp_dir

    if path.is_dir():
        pdfs = [(str(f), f.name) for f in sorted(path.iterdir())
                if f.suffix.lower() == ".pdf" and f.is_file()]
        if not pdfs:
            print(f"ERROR: No hay PDFs en: {origen}")
            sys.exit(1)
        return pdfs, None

    if path.suffix.lower() == ".pdf":
        return [(str(path), path.name)], None

    print(f"ERROR: No es PDF, carpeta ni ZIP: {origen}")
    sys.exit(1)


def procesar(origen: str, dry_run: bool = False):
    pdfs, temp_dir = _encontrar_pdfs(origen)
    using_temp = temp_dir is not None

    if using_temp:
        destino_base = Path(origen).parent / f"{Path(origen).stem}_renombrados"
        destino_base.mkdir(parents=True, exist_ok=True)
    else:
        destino_base = Path(origen)

    print(f"\n{'='*65}")
    print(f"  RENOMBRADOR DE PDFS — {'SIMULACION' if dry_run else 'EJECUTANDO'}")
    print(f"{'='*65}")
    print(f"  Origen: {origen}")
    if using_temp:
        print(f"  Destino: {destino_base}")
    print(f"{'='*65}\n")

    resultados = []
    errores = []

    for fullpath, fname in pdfs:
        data = _extraer_de_pdf(fullpath)
        if data is None:
            errores.append((fname, "No se pudo leer el PDF"))
            continue

        new_name = f"{data['numero']} - {data['corto']} - {data['mes']} {data['anio']}.pdf"
        resultados.append((fullpath, new_name))

        if dry_run:
            print(f"  {fname:50s} → {new_name}")
            print(f"    Razón social: {data['razon_social']}")
        else:
            print(f"  {fname:50s} → {new_name}")

    for fname, err in errores:
        print(f"  ✗ {fname:50s} → {err}")

    if not dry_run and resultados:
        ok = 0
        for old_path_str, new_name in resultados:
            old_path = Path(old_path_str)
            if using_temp:
                dest = destino_base / new_name
                if dest.exists():
                    print(f"  ✗ YA EXISTE: {new_name}")
                    continue
                shutil.copy2(old_path_str, str(dest))
                ok += 1
            else:
                new_path = old_path.parent / new_name
                if new_path.exists():
                    print(f"  ✗ YA EXISTE: {new_name}")
                    continue
                old_path.rename(new_path)
                ok += 1
        print(f"\n  ✅ {ok} archivos renombrados.")
    elif dry_run and resultados:
        print(f"\n  📋 Simulación — no se modificó ningún archivo.")

    if using_temp and temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Renombrador inteligente de PDFs de facturas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  %(prog)s "C:/ruta/carpeta"              # Renombrar PDFs en carpeta
  %(prog)s "C:/ruta/archivo.zip"          # Renombrar desde ZIP
  %(prog)s "C:/ruta/carpeta" --dry-run    # Simular sin renombrar
        """,
    )
    parser.add_argument("origen", nargs="?", default=None,
                        help="Carpeta, ZIP o PDF individual")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo mostrar cambios, no modificar archivos")

    args = parser.parse_args()
    if not args.origen:
        parser.print_help()
        sys.exit(1)

    procesar(args.origen, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
