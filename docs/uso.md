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
Total de palabras: 8,432

1. DENSIDAD DE MARCADORES LLM
   Densidad: 11.58 por 1000 palabras
   Interpretación: ALTA — indicio fuerte de asistencia por LLM
   Top marcadores:
     - unprecedented: 5
     - bridge the gap: 7
     - transformative: 4
     - paradigm shift: 3
     ...

2. REDUNDANCIA INTERNA
   3 pares con similitud >= 0.7
     - P4 ~ P17: 0.847
     - P12 ~ P23: 0.731
     ...

3. VERIFICACIÓN DE CITAS (CrossRef)
   DOIs detectados: 17
   Verificadas: 10/17
     [OK ] 10.1186/s12931-025-03340-4
            Phase 2 clinical trial of PIPE-791 in pulmonary fibrosis
     [XX ] 10.9999/inexistente.2025
     ...
```

## Opciones del CLI

| Opción | Descripción |
|---|---|
| `--idioma en` / `--idioma es` | Idioma del texto. Default `en`. Cambia el vocabulario marcador usado. |
| `--json` | Salida en JSON en lugar del formato legible. Útil para pipelines. |
| `--sin-citas` | Salta la verificación contra CrossRef. Mucho más rápido. |
| `--max-citas N` | Máximo de DOIs a verificar (default 20). Cada verificación es una llamada HTTP. |

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
UMBRAL_SIMILITUD_PARRAFOS = 0.7  # 0-1
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
