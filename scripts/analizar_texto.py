#!/usr/bin/env python3
"""
analizar_texto.py — Análisis de autenticidad de textos académicos.

Detecta:
  1. Densidad de vocabulario marcador típico de LLMs.
  2. Redundancia semántica entre párrafos (TF-IDF + cosine similarity).
  3. Verificación de citas:
       a) DOIs explícitos contra CrossRef (/works/{doi}).
       b) Citas autor-año extraídas del texto, buscadas en CrossRef search.
  4. Estadísticas generales del texto.

Uso básico:
    python analizar_texto.py manuscrito.txt
    python analizar_texto.py manuscrito.txt --idioma es
    python analizar_texto.py manuscrito.txt --json > reporte.json

Configura tu email para la etiqueta de CrossRef:
    export CROSSREF_MAILTO="tu@correo.com"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


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
    "revolucionar",
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
UMBRAL_DENSIDAD_BAJA = 3.0            # marcadores por 1000 palabras
UMBRAL_DENSIDAD_ALTA = 8.0
UMBRAL_SIMILITUD_PARRAFOS = 0.5       # similitud coseno 0-1 (TF-IDF)
LONGITUD_MINIMA_PARRAFO = 100         # caracteres

EMAIL_CONTACTO = os.environ.get("CROSSREF_MAILTO", "toolkit-user@example.com")
USER_AGENT = f"text-authenticity-toolkit (mailto:{EMAIL_CONTACTO})"

# ==============================================================
# Patrones para extraer citas autor-año
# ==============================================================
# Captura cosas como:
#   (Selman et al., 2025)
#   (Selman and Pardo, 2020)
#   (Selman & Pardo, 2020)
#   (Selman, 2020)
#   Selman et al. (2025)
#   Selman (2020)
# re.DOTALL/\s+ para que los saltos de línea internos no rompan la captura
# (texto desde pandoc-docx puede tener "Author et\nal., 2025" por wrap)
RE_CITA_PARENS = re.compile(
    r"\(\s*"
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+"                          # apellido primero
    r"(?:\s+et\s+al\.?)?"                                   # opcional "et al."
    r"(?:\s*(?:&|and|y)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+)?"     # opcional segundo apellido
    r")\s*,?\s*"
    r"(\d{4})[a-z]?"                                        # año
    r"\s*\)",
    flags=re.DOTALL,
)
RE_CITA_INLINE = re.compile(
    r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+"
    r"(?:\s+et\s+al\.?)?"
    r"(?:\s*(?:&|and|y)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]+)?)"
    r"\s*\(\s*(\d{4})[a-z]?\s*\)",
    flags=re.DOTALL,
)

# Stop-words mínimas en inglés/español para extraer keywords del contexto
# y pasarlos a CrossRef como query.bibliographic. Reduce falsos positivos.
STOP_WORDS_CONTEXTO = {
    "the", "and", "for", "with", "from", "that", "this", "these", "those",
    "have", "has", "had", "was", "were", "been", "being", "are", "but",
    "not", "can", "will", "may", "also", "such", "both", "into", "than",
    "then", "them", "they", "their", "there", "which", "when", "where",
    "while", "some", "more", "most", "other", "only", "over", "under",
    "about", "after", "before", "between", "through", "however", "furthermore",
    "moreover", "therefore", "thus", "hence",
    "los", "las", "del", "por", "para", "con", "sin", "que", "como",
    "esta", "este", "estos", "estas", "una", "unos", "unas",
}


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


def detectar_redundancia(texto: str, umbral: float = UMBRAL_SIMILITUD_PARRAFOS,
                         idioma: str = "en"):
    """
    Detecta pares de párrafos redundantes usando TF-IDF + similitud coseno.
    Captura tanto duplicación literal (sim≈1.0) como redundancia temática
    (ej. múltiples párrafos reformulando el mismo contenido).
    """
    parrafos = [
        p.strip() for p in texto.split("\n\n")
        if len(p.strip()) > LONGITUD_MINIMA_PARRAFO
    ]
    if len(parrafos) < 2:
        return []

    stop_words = "english" if idioma == "en" else None
    try:
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words=stop_words,
            min_df=1,
            max_df=0.95,
        )
        matriz = vectorizer.fit_transform(parrafos)
    except ValueError:
        return []

    sim = cosine_similarity(matriz)
    pares = []
    for i in range(len(parrafos)):
        for j in range(i + 1, len(parrafos)):
            if sim[i, j] >= umbral:
                pares.append({
                    "parrafo_a": i + 1,
                    "parrafo_b": j + 1,
                    "similitud": round(float(sim[i, j]), 3),
                    "extracto_a": parrafos[i][:120] + "...",
                    "extracto_b": parrafos[j][:120] + "...",
                })
    pares.sort(key=lambda p: -p["similitud"])
    return pares


def extraer_dois(texto: str) -> list[str]:
    patron = r"10\.\d{4,9}/[-._;()/:A-Z0-9]+"
    return sorted(set(re.findall(patron, texto, flags=re.IGNORECASE)))


def _normalizar_ws(s: str) -> str:
    """Colapsa todo whitespace (incluyendo \\n) en un solo espacio."""
    return re.sub(r"\s+", " ", s).strip()


def _extraer_keywords_contexto(contexto: str, n: int = 8) -> list[str]:
    """Extrae hasta n palabras largas del contexto, excluyendo stop-words."""
    palabras = re.findall(r"\b[a-zA-Z][a-zA-Z\-]{3,}\b", contexto)
    seen = set()
    keywords = []
    for p in palabras:
        pl = p.lower()
        if pl in STOP_WORDS_CONTEXTO or pl in seen:
            continue
        seen.add(pl)
        keywords.append(p)
        if len(keywords) >= n:
            break
    return keywords


def extraer_citas_autor_anio(texto: str, ventana: int = 200):
    """
    Extrae tuplas (autor, año, contexto) del texto en formato autor-año.
    El contexto son los ±ventana caracteres alrededor de la cita, usado
    después para dar a CrossRef una query bibliográfica y reducir falsos
    positivos al buscar solo por apellido+año.
    """
    encontradas = []
    for patron in (RE_CITA_PARENS, RE_CITA_INLINE):
        for m in patron.finditer(texto):
            autor = _normalizar_ws(m.group(1))
            anio = int(m.group(2))
            if not (1900 <= anio <= 2100):
                continue
            inicio = max(0, m.start() - ventana)
            fin = min(len(texto), m.end() + ventana)
            contexto = _normalizar_ws(texto[inicio:fin])
            encontradas.append((autor, anio, contexto))
    # Dedup por (autor_lower, año), concatenando contextos para dar más señal
    por_clave: dict[tuple[str, int], tuple[str, int, str]] = {}
    for autor, anio, ctx in encontradas:
        clave = (autor.lower(), anio)
        if clave not in por_clave:
            por_clave[clave] = (autor, anio, ctx)
        else:
            a0, y0, c0 = por_clave[clave]
            if ctx not in c0:
                por_clave[clave] = (a0, y0, (c0 + " " + ctx)[:2000])
    return sorted(por_clave.values(), key=lambda t: (t[0].lower(), t[1]))


def verificar_doi_crossref(doi: str) -> dict:
    url = f"https://api.crossref.org/works/{doi}"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
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


def verificar_cita_autor_anio(autor: str, anio: int,
                              contexto: str | None = None) -> dict:
    """
    Busca en CrossRef un paper que coincida con autor+año. Si se da un
    contexto (párrafo donde aparece la cita), se extraen keywords y se
    pasan a query.bibliographic para reducir falsos positivos por
    homonimia de apellidos.
    """
    autor_limpio = re.sub(r"\s+et\s+al\.?$", "", autor, flags=re.IGNORECASE).strip()
    autor_limpio = re.sub(r"\s*(?:&|and|y)\s+.*$", "", autor_limpio).strip()
    apellido_citado = autor_limpio.split()[0] if autor_limpio else ""

    params = {
        "query.author": autor_limpio,
        "filter": f"from-pub-date:{anio},until-pub-date:{anio}",
        "rows": 3,
        "select": "DOI,title,author,issued,container-title",
    }
    if contexto:
        keywords = _extraer_keywords_contexto(contexto, n=8)
        if keywords:
            params["query.bibliographic"] = " ".join(keywords)

    try:
        r = requests.get(
            "https://api.crossref.org/works",
            params=params,
            timeout=15,
            headers={"User-Agent": USER_AGENT},
        )
        if r.status_code != 200:
            return {
                "autor_citado": autor, "anio_citado": anio,
                "encontrado": False, "status": r.status_code,
            }
        items = r.json().get("message", {}).get("items", [])
        if not items:
            return {
                "autor_citado": autor, "anio_citado": anio,
                "encontrado": False,
                "nota": "Sin coincidencias en CrossRef para autor+año",
            }

        # Entre los top candidatos, elegir el primero cuyo primer autor
        # contenga el apellido citado. Si ninguno coincide, tomar el top 1.
        elegido = items[0]
        for item in items:
            primer_family = (item.get("author", [{}])[0].get("family", "")
                             if item.get("author") else "")
            if apellido_citado.lower() in primer_family.lower():
                elegido = item
                break

        anio_real = (elegido.get("issued", {}).get("date-parts", [[None]])[0]
                     or [None])[0]
        autores_reales = [a.get("family", "") for a in elegido.get("author", [])[:5]]
        primer_autor = autores_reales[0] if autores_reales else ""
        # Matching permisivo: el apellido citado aparece en el family del primer
        # autor (maneja casos donde CrossRef tiene nombre+apellido en family)
        coincide_apellido = (
            apellido_citado.lower() in primer_autor.lower()
            if primer_autor and apellido_citado
            else False
        )
        return {
            "autor_citado": autor,
            "anio_citado": anio,
            "encontrado": True,
            "titulo": (elegido.get("title") or [""])[0],
            "doi": elegido.get("DOI"),
            "autores_reales": autores_reales,
            "anio_real": anio_real,
            "coincide_apellido_con_primer_autor": coincide_apellido,
            "advertencia": None if coincide_apellido else (
                f'El primer autor real es "{primer_autor}", '
                f'pero la cita dice "{apellido_citado}". '
                f"Posible atribución incorrecta o match ambiguo en CrossRef."
            ),
        }
    except requests.RequestException as e:
        return {
            "autor_citado": autor, "anio_citado": anio,
            "encontrado": False, "error": str(e),
        }


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

    print("\n2. REDUNDANCIA SEMÁNTICA (TF-IDF + cosine)")
    if r["parrafos_redundantes"]:
        print(f"   {len(r['parrafos_redundantes'])} pares con similitud >= "
              f"{UMBRAL_SIMILITUD_PARRAFOS}")
        for p in r["parrafos_redundantes"][:8]:
            print(f"     - P{p['parrafo_a']} ~ P{p['parrafo_b']}: {p['similitud']}")
    else:
        print("   Sin redundancia significativa detectada")

    print("\n3a. VERIFICACIÓN DE DOIs (CrossRef /works/{doi})")
    print(f"    DOIs detectados: {r['dois_detectados']}")
    if r["dois_verificados"]:
        encontradas = sum(1 for c in r["dois_verificados"] if c.get("encontrado"))
        print(f"    Verificados: {encontradas}/{len(r['dois_verificados'])}")
        for c in r["dois_verificados"]:
            estado = "OK " if c.get("encontrado") else "XX "
            print(f"      [{estado}] {c['doi']}")
            if c.get("encontrado"):
                print(f"             {c.get('titulo', '')[:70]}")

    print("\n3b. VERIFICACIÓN DE CITAS AUTOR-AÑO (CrossRef search)")
    print(f"    Citas autor-año detectadas: {r['citas_autor_anio_detectadas']}")
    if r["citas_autor_anio_verificadas"]:
        encontradas = sum(1 for c in r["citas_autor_anio_verificadas"]
                          if c.get("encontrado"))
        coincide = sum(1 for c in r["citas_autor_anio_verificadas"]
                       if c.get("coincide_apellido_con_primer_autor"))
        print(f"    Encontradas en CrossRef: {encontradas}/"
              f"{len(r['citas_autor_anio_verificadas'])}")
        print(f"    Con apellido coincidente: {coincide}")
        print("    Detalle:")
        for c in r["citas_autor_anio_verificadas"]:
            if c.get("encontrado"):
                marca = "OK " if c.get("coincide_apellido_con_primer_autor") else "?? "
            else:
                marca = "XX "
            etiqueta = f"{c['autor_citado']}, {c['anio_citado']}"
            print(f"      [{marca}] {etiqueta}")
            if c.get("advertencia"):
                print(f"             -> {c['advertencia']}")
            if c.get("encontrado") and c.get("anio_real") != c.get("anio_citado"):
                print(f"             -> Año real: {c['anio_real']} (citado: {c['anio_citado']})")

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
                        help="Saltar verificación de CrossRef (DOIs y autor-año)")
    parser.add_argument("--max-citas", type=int, default=20,
                        help="Máximo de DOIs a verificar (default: 20)")
    parser.add_argument("--max-citas-texto", type=int, default=30,
                        help="Máximo de citas autor-año a verificar (default: 30)")
    parser.add_argument("--sin-citas-texto", action="store_true",
                        help="Saltar verificación de citas autor-año")
    args = parser.parse_args()

    texto = cargar_texto(args.archivo)
    marcadores = MARCADORES_ES if args.idioma == "es" else MARCADORES_EN

    conteos, densidad, total_palabras = calcular_densidad(texto, marcadores)
    redundancias = detectar_redundancia(texto, idioma=args.idioma)
    dois = extraer_dois(texto)
    citas_texto = extraer_citas_autor_anio(texto)

    dois_verificados = []
    if not args.sin_citas and dois:
        print(f"Verificando {min(len(dois), args.max_citas)} DOIs en CrossRef...",
              file=sys.stderr)
        for doi in dois[:args.max_citas]:
            dois_verificados.append(verificar_doi_crossref(doi))

    citas_texto_verificadas = []
    if not args.sin_citas and not args.sin_citas_texto and citas_texto:
        n = min(len(citas_texto), args.max_citas_texto)
        print(f"Verificando {n} citas autor-año en CrossRef...", file=sys.stderr)
        for autor, anio, ctx in citas_texto[:args.max_citas_texto]:
            citas_texto_verificadas.append(
                verificar_cita_autor_anio(autor, anio, contexto=ctx)
            )

    resultado = {
        "archivo": args.archivo,
        "idioma": args.idioma,
        "total_palabras": total_palabras,
        "densidad_marcadores_por_1000": round(densidad, 2),
        "interpretacion_densidad": interpretar_densidad(densidad),
        "marcadores_encontrados": dict(sorted(conteos.items(), key=lambda x: -x[1])),
        "parrafos_redundantes": redundancias,
        "dois_detectados": len(dois),
        "dois_verificados": dois_verificados,
        "citas_autor_anio_detectadas": len(citas_texto),
        "citas_autor_anio_verificadas": citas_texto_verificadas,
    }

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        imprimir_reporte_legible(resultado)


if __name__ == "__main__":
    main()
