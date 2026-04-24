# Guía de uso

## Instalación

```bash
git clone https://github.com/USUARIO/text-authenticity-toolkit.git
cd text-authenticity-toolkit
pip install -r requirements.txt
```

Requiere Python 3.9 o superior.

## Preparación del texto

El analizador espera un archivo `.txt` en UTF-8. Si tu manuscrito está en `.docx` o `.pdf`, conviértelo primero:

```bash
# .docx → .txt
pandoc manuscrito.docx -o manuscrito.txt

# .pdf → .txt
pdftotext manuscrito.pdf manuscrito.txt
```

Coloca el archivo en `data/raw/` (esta carpeta está en `.gitignore`, no se versionará).

## Ejecución básica

```bash
python scripts/analizar_texto.py data/raw/manuscrito.txt
```

Salida ejemplo:

```
============================================================
ANÁLISIS DE AUTENTICIDAD — data/raw/manuscrito.txt
============================================================

Idioma analizado: en
Total de palabras: 3,678

1. DENSIDAD DE MARCADORES LLM
   Densidad: 13.32 por 1000 palabras
   Interpretación: ALTA — indicio fuerte de asistencia por LLM
   Top marcadores:
     - furthermore: 7
     - synergy: 5
     - unprecedented: 4
     ...

2. REDUNDANCIA SEMÁNTICA (TF-IDF + cosine)
   Sin redundancia significativa detectada

3a. VERIFICACIÓN DE DOIs (CrossRef /works/{doi})
    DOIs detectados: 0

3b. VERIFICACIÓN DE CITAS AUTOR-AÑO (CrossRef search)
    Citas autor-año detectadas: 26
    Encontradas en CrossRef: 26/26
    Con apellido coincidente: 20
    Detalle:
      [OK ] Aggarwal et al., 2025
      [OK ] Alsafadi et al., 2020
      [?? ] Zhang et al., 2023
             -> El primer autor real es "Wu", pero la cita dice "Zhang".
                Posible atribución incorrecta o match ambiguo en CrossRef.
      ...
```

### Cómo leer las verificaciones de citas

| Marca | Significado | Acción recomendada |
|---|---|---|
| `[OK ]` | CrossRef encontró un paper con el apellido citado como primer autor en el año citado. | Confiar, pero ojo: un match por apellido+año no confirma que la cita sea **la correcta** — un autor puede tener varios papers en el mismo año. |
| `[?? ]` | CrossRef devolvió un paper pero el primer autor no coincide con el citado. | **Revisar manualmente en PubMed/Google Scholar.** Puede ser atribución incorrecta real o un falso positivo si el apellido es común. |
| `[XX ]` | CrossRef no encontró ningún paper con ese autor+año. | **Alta probabilidad de cita alucinada** o publicación en un venue no indexado (preprint pre-DOI, libro, patente). |

## Opciones del CLI

| Opción | Descripción |
|---|---|
| `--idioma en` / `--idioma es` | Idioma del texto. Default `en`. Cambia el vocabulario marcador y las stop-words del TF-IDF. |
| `--json` | Salida en JSON en lugar del formato legible. Útil para pipelines. |
| `--sin-citas` | Salta TODA verificación contra CrossRef (DOIs y autor-año). Mucho más rápido. |
| `--sin-citas-texto` | Salta solo la verificación autor-año; los DOIs sí se verifican. |
| `--max-citas N` | Máximo de DOIs a verificar (default 20). Cada verificación es una llamada HTTP. |
| `--max-citas-texto N` | Máximo de citas autor-año a verificar (default 30). |

### Variable de entorno

| Variable | Descripción |
|---|---|
| `CROSSREF_MAILTO` | Email para el header User-Agent de CrossRef. Default `toolkit-user@example.com`. Configúralo con tu email real: ayuda a que CrossRef te contacte si hay problemas de uso. |

```bash
export CROSSREF_MAILTO="tu@correo.com"
python scripts/analizar_texto.py data/raw/manuscrito.txt
```

## Casos de uso comunes

### A. Evaluación rápida sin internet

```bash
python scripts/analizar_texto.py data/raw/manuscrito.txt --sin-citas
```

### B. Generar reporte JSON para adjuntar a evaluación formal

```bash
python scripts/analizar_texto.py data/raw/manuscrito.txt --json > results/reporte.json
```

### C. Verificar todas las citas de un review extenso

```bash
python scripts/analizar_texto.py data/raw/manuscrito.txt --max-citas 100
```

### D. Análisis en español

```bash
python scripts/analizar_texto.py data/raw/tesis.txt --idioma es
```

### E. Comparar dos versiones (antes/después de edición)

```bash
python scripts/analizar_texto.py data/raw/v1.txt --json > results/v1.json
python scripts/analizar_texto.py data/raw/v2.txt --json > results/v2.json
diff <(jq '.marcadores_encontrados' results/v1.json) \
     <(jq '.marcadores_encontrados' results/v2.json)
```

## Personalización

### Ajustar vocabulario marcador

Edita `scripts/analizar_texto.py`, secciones `MARCADORES_EN` y `MARCADORES_ES`. Añade términos específicos de tu dominio. Por ejemplo, para reviews biomédicos podrías añadir:

```python
MARCADORES_EN += [
    "holistic approach", "cutting-edge", "state-of-the-art",
    "groundbreaking", "pave the way", "shed light on",
]
```

### Ajustar umbrales de interpretación

```python
UMBRAL_DENSIDAD_BAJA = 3.0       # marcadores / 1000 palabras
UMBRAL_DENSIDAD_ALTA = 8.0
UMBRAL_SIMILITUD_PARRAFOS = 0.5  # similitud coseno TF-IDF, 0-1
```

En campos con estilo típicamente más elaborado (humanidades, review papers), sube los umbrales. En textos experimentales primarios (methods, results), bájalos.

## Integración con flujos editoriales

Este script produce evidencia **objetiva complementaria**. Para una evaluación formal:

1. Corre el script y guarda el JSON como anexo.
2. Corre Grammarly Authorship / GPTZero / Originality.ai y guarda screenshots.
3. Pasa el manuscrito por Turnitin / iThenticate para plagio tradicional.
4. Lee el manuscrito críticamente y combina las tres fuentes de evidencia.

El patrón recomendado para la evaluación al autor:

> "El análisis automatizado detectó N citas con problemas de verificación (ver anexo). Estos son hechos verificables independientes del detector de IA usado. Adicionalmente, el detector probabilístico arrojó X% de asistencia por IA, lo cual debe interpretarse como evidencia complementaria con tasas de error conocidas."

## Troubleshooting

### "requests.exceptions.Timeout"

CrossRef está tardando. Reintenta con `--max-citas 5` o usa `--sin-citas` y verifica los DOIs manualmente en https://doi.org/.

### "Total de palabras: 0"

El archivo no se leyó correctamente. Verifica que esté en UTF-8:

```bash
file data/raw/manuscrito.txt
iconv -f ISO-8859-1 -t UTF-8 manuscrito.txt > manuscrito-utf8.txt
```

### Densidad muy alta en texto humano conocido

Tu dominio probablemente usa legítimamente algunas de las palabras de la lista. Revisa `MARCADORES_EN` y quita las que sean falsos positivos en tu campo.
