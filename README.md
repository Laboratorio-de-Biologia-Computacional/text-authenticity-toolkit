# text-authenticity-toolkit

Kit de herramientas para evaluar la autenticidad, originalidad y posible asistencia por IA en textos académicos (manuscritos, reviews, tesis, ensayos). Combina análisis estilístico, detección de redundancia interna y verificación objetiva de citas vía CrossRef.

## ¿Qué hace?

- **Señales de contenido generado por LLM**: densidad de vocabulario marcador (*unprecedented*, *paradigm shift*, *bridge the gap*, etc.) por cada 1000 palabras, con interpretación automática.
- **Redundancia semántica** (TF-IDF + cosine): detecta párrafos duplicados o reformulaciones con vocabulario compartido dentro del mismo documento (patrón típico de edición descuidada post-generación).
- **Verificación de citas en dos modalidades**:
  - **DOIs explícitos** → CrossRef `/works/{doi}` para confirmar existencia y metadatos.
  - **Citas autor-año** `(Autor et al., AÑO)` → CrossRef search con keywords del contexto para detectar citas alucinadas o mal atribuidas.
- **Estadísticas generales**: conteo de palabras, distribución de marcadores, pares redundantes.

## Filosofía

Los detectores probabilísticos de IA (GPTZero, Originality.ai, Grammarly Authorship) tienen tasas conocidas de falsos positivos, especialmente en:

- Autores no nativos de inglés
- Textos académicos muy formales
- Textos editados o parafraseados

Este kit **no reemplaza** esos detectores, pero los complementa con **evidencia objetiva y auditable**: una cita con DOI inexistente es un hecho verificable, no una probabilidad.

## Estructura del proyecto

```
text-authenticity-toolkit/
├── README.md              # este archivo (bilingüe)
├── LICENSE                # MIT
├── .gitignore             # excluye data/ y results/ por privacidad
├── requirements.txt       # dependencias Python
├── scripts/
│   └── analizar_texto.py  # analizador principal
├── data/
│   ├── raw/               # textos de entrada (NO versionados)
│   └── processed/         # texto limpio intermedio
├── results/               # reportes de salida (NO versionados)
├── examples/
│   ├── README.md          # cómo interpretar los ejemplos
│   └── sample_output.txt  # salida demo sobre texto ficticio
└── docs/
    ├── metodologia.md     # qué detecta y por qué
    └── uso.md             # guía paso a paso
```

## Colaboradores

- Dra. Yalbi I. Balderas-Martínez — Investigadora, Instituto Nacional de Enfermedades Respiratorias (INER)

## Herramientas

- Python 3.9+
- [`requests`](https://pypi.org/project/requests/) — cliente HTTP para la API de CrossRef
- [`scikit-learn`](https://pypi.org/project/scikit-learn/) — TF-IDF y similitud coseno para detección de redundancia
- [CrossRef API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) — verificación de DOIs y búsqueda autor-año (pública, sin API key)

## Cómo usarlo

```bash
# 1. Clonar e instalar dependencias
git clone https://github.com/USUARIO/text-authenticity-toolkit.git
cd text-authenticity-toolkit
pip install -r requirements.txt

# 2. Colocar el texto a analizar en data/raw/
cp /ruta/a/manuscrito.txt data/raw/

# 3. Ejecutar el análisis
python scripts/analizar_texto.py data/raw/manuscrito.txt

# Opciones comunes:
python scripts/analizar_texto.py data/raw/manuscrito.txt --idioma es
python scripts/analizar_texto.py data/raw/manuscrito.txt --json > results/reporte.json
python scripts/analizar_texto.py data/raw/manuscrito.txt --sin-citas     # más rápido
python scripts/analizar_texto.py data/raw/manuscrito.txt --max-citas 50  # verificar más DOIs
```

Ver [`docs/uso.md`](docs/uso.md) para la guía completa y [`docs/metodologia.md`](docs/metodologia.md) para entender cómo interpretar los resultados.

## Limitaciones importantes

1. **No es un detector de IA certificado**. No da un "porcentaje de IA" tipo Turnitin.
2. **El vocabulario marcador es para inglés** por defecto (configurable en el script); hay una lista básica para español.
3. **No detecta plagio tradicional** (comparación contra bases de datos académicas). Para eso usa Turnitin o iThenticate.
4. **CrossRef no cubre todo**: algunas revistas, preprints (bioRxiv, medRxiv) y libros pueden no estar ahí.

## Licencia

MIT — ver [LICENSE](LICENSE).

---

## English

Toolkit for evaluating authenticity, originality, and possible AI-assistance in academic texts (manuscripts, reviews, theses, essays). Combines stylistic analysis, internal redundancy detection, and objective citation verification via CrossRef.

### What it does

- **LLM-generated content signals**: density of marker vocabulary (*unprecedented*, *paradigm shift*, *bridge the gap*, etc.) per 1000 words, with automatic interpretation.
- **Semantic redundancy** (TF-IDF + cosine): detects duplicated paragraphs or reformulations sharing vocabulary within the same document (typical pattern of careless post-generation editing).
- **Citation verification in two modalities**:
  - **Explicit DOIs** → CrossRef `/works/{doi}` to confirm existence and metadata.
  - **Author-year citations** `(Author et al., YEAR)` → CrossRef search with context keywords to detect hallucinated or misattributed references.
- **General statistics**: word count, marker distribution, redundant pairs.

### Philosophy

Probabilistic AI detectors (GPTZero, Originality.ai, Grammarly Authorship) have known false-positive rates, especially on non-native English authors, highly formal academic texts, and edited/paraphrased content. This toolkit **does not replace** them but complements them with **objective, auditable evidence**: a DOI that doesn't exist is a verifiable fact, not a probability.

### Quick usage

```bash
git clone https://github.com/USER/text-authenticity-toolkit.git
cd text-authenticity-toolkit
pip install -r requirements.txt
python scripts/analizar_texto.py path/to/manuscript.txt
```

See [`docs/uso.md`](docs/uso.md) for full usage and [`docs/metodologia.md`](docs/metodologia.md) for methodology.

### Limitations

Not a certified AI detector, marker vocabulary defaults to English, does not compare against plagiarism databases, and CrossRef does not cover all preprints or books.

### License

MIT — see [LICENSE](LICENSE).
