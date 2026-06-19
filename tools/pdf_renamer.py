#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta: Renombrador Inteligente de PDFs
=============================================
Lee facturas PDF, extrae proveedor y fecha del contenido,
y renombra los archivos con el formato:

    {numero} - {PROVEEDOR_CORTO} - {MES AÑO}.pdf

Incluye deteccion automatica de conflictos: si dos proveedores
comparten la misma marca (ej: ENEL Distribucion / ENEL Generacion),
los diferencia incluyendo la palabra de giro.

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

# Conectores y articulos
_STOP = {
    "de", "del", "de la", "de las", "de los", "y", "e", "el", "la",
    "los", "las", "un", "una", "en", "al", "por", "para", "con",
}

# Sufijos legales (orden: mas especifico primero)
_SUFIJOS = [
    " SpA", " S.A.", " S.A", " SA", " Ltda", " Limitada",
    " E.I.R.L.", " EIRL",
]

# Palabras de giro generico (no aportan identidad)
# NOTA: 'distribucion', 'generacion', 'transmision' NO estan aqui
# porque diferencian empresas como ENEL Distribucion vs ENEL Generacion
_GIRO = {
    "arriendo", "compra", "venta", "bienes", "inmuebles",
    "amoblados", "equipos", "maquinarias",
    "logistico", "logístico", "centro",
    "comercial", "industrial", "profesional",
    "sociedad", "empresa", "nacional", "general",
}

# Geograficos (nunca identidad)
_GEO = {"chile", "santiago", "region", "regional", "metropolitana"}


def _abreviar_proveedor(razon_social: str) -> str:
    """Deriva nombre corto (~10-12 chars) desde la razon social.

    Para no-Megacentro usa siempre los primeros 2 tokens significativos
    (marca + giro), asi 'ENEL Distribucion' → ENELDISTRI (no solo ENEL).
    """
    nombre = razon_social.strip()

    # ── 1. Quitar sufijos legales ──
    nombre_upper = nombre.upper()
    for suf in _SUFIJOS:
        if nombre_upper.endswith(suf.upper()):
            nombre = nombre[:-len(suf)].strip()
            break

    # ── 2. Separar por guion → parte derecha es identidad ──
    if " - " in nombre:
        partes = nombre.split(" - ")
        if len(partes) >= 2:
            nombre = partes[-1].strip()

    # ── 3. Tokenizar y limpiar ──
    nombre_clean = re.sub(r'[^\w\s]', ' ', nombre)
    tokens = nombre_clean.split()
    tokens = [t for t in tokens if t.lower() not in _STOP]
    tokens = [t for t in tokens if t.lower() not in _GEO]
    tokens = [t for t in tokens if t.lower() not in _GIRO]

    if not tokens:
        tokens = [t for t in nombre_clean.split() if t.lower() not in _STOP]
        tokens = [t for t in tokens if t.lower() not in _GEO]
    if not tokens:
        return "DESCONOCIDO"

    # ── 4. Grupo Megacentro: prefijo MEGA + ultima palabra clave ──
    full_upper = razon_social.upper()
    if "MEGACENTRO" in full_upper or full_upper.startswith("RENTAS"):
        clave = tokens[-1].upper()
        if len(clave) > 8:
            clave = clave[:6]
        return f"MEGA{clave}"

    # ── 5. Otros proveedores: primeros 2 tokens = marca + tipo ──
    # Tomar hasta 2 tokens y abreviar: primero + segundo[:6]
    p1 = tokens[0].upper()[:6]
    if len(tokens) >= 2:
        p2 = tokens[1].upper()[:6]
        return f"{p1}{p2}"
    return p1


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
    except Exception:
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
    """Retorna (lista (ruta_completa, nombre_relativo), temp_dir_opcional)."""
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
        pdfs = []
        for f in sorted(path.rglob("*.pdf")):
            if f.is_file():
                rel = str(f.relative_to(path))
                pdfs.append((str(f), rel))
        if not pdfs:
            print(f"ERROR: No hay PDFs en: {origen}")
            sys.exit(1)
        return pdfs, None

    if path.suffix.lower() == ".pdf":
        return [(str(path), path.name)], None

    print(f"ERROR: No es PDF, carpeta ni ZIP: {origen}")
    sys.exit(1)


def procesar(origen: str, dry_run: bool = False) -> dict:
    """Renombra PDFs. Retorna dict con resultados estructurados."""
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
    output_lines = []

    for fullpath, fname in pdfs:
        data = _extraer_de_pdf(fullpath)
        if data is None:
            errores.append({"archivo": fname, "error": "No se pudo leer el PDF"})
            output_lines.append(f"  ✗ {fname:50s} → No se pudo leer")
            continue

        destino = (
            f"{data['numero']} - {data['corto']} - "
            f"{data['mes']} {data['anio']}.pdf"
        )
        resultados.append({
            "origen": fname,
            "destino": destino,
            "fullpath": fullpath,
            "numero": data["numero"],
            "proveedor": data["corto"],
            "mes": data["mes"],
            "anio": data["anio"],
            "razon_social": data["razon_social"],
        })
        output_lines.append(f"  {fname:50s} → {destino}")
        if dry_run:
            output_lines.append(f"    Razón social: {data['razon_social']}")

    # ── Ejecutar renombre ──
    if not dry_run and resultados:
        ok = 0
        for item in resultados:
            old_path = Path(item["fullpath"])
            new_name = item["destino"]
            if using_temp:
                dest = destino_base / new_name
                if dest.exists():
                    item["estado"] = "ya_existe"
                    continue
                shutil.copy2(str(old_path), str(dest))
                ok += 1
                item["estado"] = "copiado"
            else:
                new_path = old_path.parent / new_name
                if new_path.exists():
                    item["estado"] = "ya_existe"
                    continue
                old_path.rename(new_path)
                ok += 1
                item["estado"] = "renombrado"

        output_lines.append(f"\n  ✅ {ok} archivos renombrados.")
    elif dry_run and resultados:
        output_lines.append(f"\n  📋 Simulación — no se modificó ningún archivo.")

    if using_temp and temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "origen": str(origen),
        "destino": str(destino_base),
        "dry_run": dry_run,
        "resultados": resultados,
        "errores": errores,
        "respuesta": "\n".join(output_lines),
    }


# ── Entry points ─────────────────────────────────────────────


def procesar_desde_cli(origen: str, dry_run: bool = False):
    """Wrapper para CLI de Nexus. Muestra output y retorna resumen."""
    res = procesar(origen, dry_run=dry_run)
    print(res["respuesta"])
    conflictos = [r["proveedor"] for r in res["resultados"]
                  if r.get("conflicto")]
    hechos = len([r for r in res["resultados"]
                  if r.get("estado") in ("renombrado", "copiado")])
    return f"Listo. {hechos} archivos procesados."


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

    res = procesar(args.origen, dry_run=args.dry_run)
    print(res["respuesta"])


if __name__ == "__main__":
    main()
