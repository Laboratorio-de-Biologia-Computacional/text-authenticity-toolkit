#!/usr/bin/env python3
"""
analizar_texto.py — Análisis de autenticidad de textos académicos.

Detecta:
  1. Densidad de vocabulario marcador típico de LLMs.
  2. Redundancia interna (párrafos similares dentro del mismo documento).
  3. Verificación de DOIs contra CrossRef.
  4. Estadísticas generales del texto.

Uso básico:
    python analizar_texto.py manuscrito.txt
    python analizar_texto.py manuscrito.txt --idioma es
    python analizar_texto.py manuscrito.txt --json > reporte.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import requests


# ==============================================================
# Vocabulario marcador de LLMs — EDITAR según dominio
# ==============================================================
# Lista organizada en dos bloques:
#   (a) Marcadores genéricos de LLM en texto académico en inglés/español.
#   (b) Marcadores específicos de biomedicina, enfermedades respiratorias
#       y medicina clínica/traslacional — dominios donde LLMs sobreusan
#       ciertas frases retóricas.
#
# NOTA sobre falsos positivos: términos técnicos legítimos como
# "next-generation sequencing", "precision medicine" o "systems biology"
# NO se incluyen aunque los LLMs los abusen — son vocabulario estándar
# del campo. Solo se listan frases retóricas inflamatorias.

MARCADORES_EN = [
    # --- Genéricos: énfasis inflado ---
    "unprecedented", "unparalleled", "transformative", "revolutionary",
    "paradigm shift", "pivotal", "landmark", "pioneering",
    # --- Genéricos: metáforas abstractas ---
    "bridge the gap", "bridging the gap", "cornerstone",
    "gold standard", "powerhouse", "seamless integration",
    "synergy", "convergence", "new era", "new frontier",
    "new roadmap",
    # --- Genéricos: estructura retórica ---
    "not merely", "it is important to note", "it should be noted",
    "furthermore", "moreover", "delve", "delving", "delves",
    "in conclusion", "in summary",
    # --- Genéricos: adjetivos abstractos sobreutilizados ---
    "intricate", "multifaceted", "nuanced", "robust", "comprehensive",

    # --- Biomédico / clínico / traslacional ---
    "cutting-edge", "state-of-the-art", "groundbreaking",
    "pave the way", "paves the way", "paving the way",
    "shed light on", "shed new light", "shedding light",
    "hallmark of", "novel insights", "novel findings",
    "underscore", "underscores", "underscoring",
    "burgeoning", "game-changer", "game-changing",
    "unlock the potential", "unlocks the potential",
    "emerging evidence", "growing body of evidence", "mounting evidence",
    "therapeutic landscape", "clinical landscape",
    "unmet medical need", "unmet need",
    "holistic approach", "revolutionize", "revolutionizes",
    "open new avenues", "new avenues",
    "promising avenue", "promising strategy",
    # --- Bioinformática / genómica (solo retóricas, no técnicas) ---
    "powerful tool", "powerful framework",
    "unprecedented resolution", "unprecedented detail",
    "deep insights", "rich insights",
    # --- Respiratorio / pulmonar (frases retóricas, no técnicas) ---
    "pulmonary health", "respiratory health outcomes",
    "respiratory disease burden",
]

MARCADORES_ES = [
    # --- Genéricos: énfasis inflado ---
    "sin precedentes", "transformador", "transformadora",
    "revolucionario", "revolucionaria",
    "cambio de paradigma", "pionero", "pionera",
    # --- Genéricos: metáforas abstractas ---
    "tender un puente", "piedra angular", "estándar de oro",
    "integración perfecta", "sinergia", "convergencia",
    "nueva era", "nueva frontera", "hoja de ruta",
    # --- Genéricos: estructura retórica ---
    "no solo", "cabe destacar", "es importante señalar",
    "en conclusión", "en resumen",
    "además", "asimismo", "por ende",
    # --- Genéricos: adjetivos abstractos sobreutilizados ---
    "intrincado", "multifacético", "robusto", "integral",

    # --- Biomédico / clínico / traslacional ---
    "vanguardia", "de última generación",
    "allanar el camino", "allana el camino",
    "abrir nuevos caminos", "abre nuevos caminos",
    "arrojar luz sobre", "arroja luz sobre",
    "sello distintivo", "nuevos hallazgos",
    "enfoque holístico", "enfoque integral",
    "necesidad médica no cubierta", "necesidad no cubierta",
    "panorama terapéutico", "panorama clínico",
    "evidencia emergente", "cuerpo creciente de evidencia",
    "revolucionar", "revolucionaria",
    "punto de inflexión",
    # --- Bioinformática / genómica (solo retóricas) ---
    "herramienta poderosa", "marco poderoso",
    "resolución sin precedentes",
    # --- Respiratorio / pulmonar (frases retóricas) ---
    "salud pulmonar", "salud respiratoria",
    "carga de enfermedad respiratoria",
]

# ==============================================================
# Umbrales de interpretación — EDITAR según necesidad
# ==============================================================
UMBRAL_DENSIDAD_BAJA = 3.0        # marcadores por 1000 palabras
UMBRAL_DENSIDAD_ALTA = 8.0
UMBRAL_SIMILITUD_PARRAFOS = 0.7   # similitud 0-1
LONGITUD_MINIMA_PARRAFO = 100     # caracteres


def cargar_texto(ruta: str) -> str:
    return Path(ruta).read_text(encoding="utf-8")


def contar_palabras(texto: str) -> int:
    return len(re.findall(r"\b\w+\b", texto))


def calcular_densidad(texto: str, marcadores: list[str]):
    texto_lower = texto.lower()
    conteos = {}
    for m in marcadores:
        patron = r"\b" + re.escape(m) + r"\b"
        n = len(re.findall(patron, texto_lower))
        if n > 0:
            conteos[m] = n
    total_marcadores = sum(conteos.values())
    total_palabras = contar_palabras(texto)
    densidad = (total_marcadores / total_palabras) * 1000 if total_palabras else 0
    return conteos, densidad, total_palabras


def interpretar_densidad(d: float) -> str:
    if d < UMBRAL_DENSIDAD_BAJA:
        return "BAJA — consistente con escritura humana"
    if d < UMBRAL_DENSIDAD_ALTA:
        return "MEDIA — revisar manualmente"
    return "ALTA — indicio fuerte de asistencia por LLM"


def detectar_redundancia(texto: str, umbral: float = UMBRAL_SIMILITUD_PARRAFOS):
    parrafos = [
        p.strip() for p in texto.split("\n\n")
        if len(p.strip()) > LONGITUD_MINIMA_PARRAFO
    ]
    pares = []
    for i, p1 in enumerate(parrafos):
        for j in range(i + 1, len(parrafos)):
            p2 = parrafos[j]
            ratio = SequenceMatcher(None, p1, p2).ratio()
            if ratio >= umbral:
                pares.append({
                    "parrafo_a": i + 1,
                    "parrafo_b": j + 1,
                    "similitud": round(ratio, 3),
                    "extracto_a": p1[:120] + "...",
                    "extracto_b": p2[:120] + "...",
                })
    return pares


def extraer_dois(texto: str) -> list[str]:
    patron = r"10\.\d{4,9}/[-._;()/:A-Z0-9]+"
    return sorted(set(re.findall(patron, texto, flags=re.IGNORECASE)))


def verificar_doi_crossref(doi: str) -> dict:
    url = f"https://api.crossref.org/works/{doi}"
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "text-authenticity-toolkit (mailto:labbic@iner.gob.mx)"
        })
        if r.status_code == 200:
            data = r.json()["message"]
            return {
                "doi": doi,
                "encontrado": True,
                "titulo": (data.get("title") or [""])[0],
                "anio": (data.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0],
                "revista": (data.get("container-title") or [""])[0] or None,
                "autores": [
                    f"{a.get('family', '')}, {a.get('given', '')}"
                    for a in data.get("author", [])[:3]
                ],
            }
        return {"doi": doi, "encontrado": False, "status": r.status_code}
    except requests.RequestException as e:
        return {"doi": doi, "encontrado": False, "error": str(e)}


def imprimir_reporte_legible(r: dict) -> None:
    print("=" * 60)
    print(f"ANÁLISIS DE AUTENTICIDAD — {r['archivo']}")
    print("=" * 60)
    print(f"\nIdioma analizado: {r['idioma']}")
    print(f"Total de palabras: {r['total_palabras']:,}")

    print("\n1. DENSIDAD DE MARCADORES LLM")
    print(f"   Densidad: {r['densidad_marcadores_por_1000']} por 1000 palabras")
    print(f"   Interpretación: {r['interpretacion_densidad']}")
    if r["marcadores_encontrados"]:
        print("   Top marcadores:")
        for palabra, n in list(r["marcadores_encontrados"].items())[:10]:
            print(f"     - {palabra}: {n}")

    print("\n2. REDUNDANCIA INTERNA")
    if r["parrafos_redundantes"]:
        print(f"   {len(r['parrafos_redundantes'])} pares con similitud >= "
              f"{UMBRAL_SIMILITUD_PARRAFOS}")
        for p in r["parrafos_redundantes"][:5]:
            print(f"     - P{p['parrafo_a']} ~ P{p['parrafo_b']}: {p['similitud']}")
    else:
        print("   Sin redundancia significativa detectada")

    print("\n3. VERIFICACIÓN DE CITAS (CrossRef)")
    print(f"   DOIs detectados: {r['dois_detectados']}")
    if r["citas_verificadas"]:
        encontradas = sum(1 for c in r["citas_verificadas"] if c.get("encontrado"))
        print(f"   Verificadas: {encontradas}/{len(r['citas_verificadas'])}")
        for c in r["citas_verificadas"]:
            estado = "OK " if c.get("encontrado") else "XX "
            print(f"     [{estado}] {c['doi']}")
            if c.get("encontrado"):
                print(f"            {c.get('titulo', '')[:70]}")

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analiza autenticidad de textos académicos."
    )
    parser.add_argument("archivo", help="Ruta al archivo .txt a analizar")
    parser.add_argument("--idioma", choices=["en", "es"], default="en",
                        help="Idioma del texto (default: en)")
    parser.add_argument("--json", action="store_true",
                        help="Salida en JSON en lugar de formato legible")
    parser.add_argument("--sin-citas", action="store_true",
                        help="Saltar verificación de DOIs en CrossRef")
    parser.add_argument("--max-citas", type=int, default=20,
                        help="Máximo de DOIs a verificar (default: 20)")
    args = parser.parse_args()

    texto = cargar_texto(args.archivo)
    marcadores = MARCADORES_ES if args.idioma == "es" else MARCADORES_EN

    conteos, densidad, total_palabras = calcular_densidad(texto, marcadores)
    redundancias = detectar_redundancia(texto)
    dois = extraer_dois(texto)

    citas_verificadas = []
    if not args.sin_citas and dois:
        print(f"Verificando {min(len(dois), args.max_citas)} DOIs en CrossRef...",
              file=sys.stderr)
        for doi in dois[:args.max_citas]:
            citas_verificadas.append(verificar_doi_crossref(doi))

    resultado = {
        "archivo": args.archivo,
        "idioma": args.idioma,
        "total_palabras": total_palabras,
        "densidad_marcadores_por_1000": round(densidad, 2),
        "interpretacion_densidad": interpretar_densidad(densidad),
        "marcadores_encontrados": dict(sorted(conteos.items(), key=lambda x: -x[1])),
        "parrafos_redundantes": redundancias,
        "dois_detectados": len(dois),
        "citas_verificadas": citas_verificadas,
    }

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        imprimir_reporte_legible(resultado)


if __name__ == "__main__":
    main()
