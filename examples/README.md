# Ejemplos

Esta carpeta contiene salidas de demostración generadas con texto ficticio. **No contiene material de terceros**; está versionada y puede compartirse públicamente.

## Archivos

- `sample_output.txt` — salida del analizador sobre un texto ficticio con densidad alta de marcadores LLM. Útil para entender el formato del reporte antes de correrlo sobre un manuscrito real.

## Cómo reproducir

El texto ficticio usado para generar `sample_output.txt` fue creado artificialmente para contener todos los patrones de interés. No se incluye en el repo porque podría usarse para "entrenar" textos que evadan el detector. Si quieres generar tu propio ejemplo:

```bash
# Escribir texto de prueba en data/raw/
python scripts/analizar_texto.py data/raw/mi_ejemplo.txt > examples/mi_output.txt
```

## Advertencia sobre material real

**Nunca commitees manuscritos, tesis o textos de terceros a este repo.** Los resultados de análisis (en `results/`) tampoco deben versionarse — están ignorados en `.gitignore`.

Si quieres compartir un caso real como ejemplo:

1. Obtén permiso explícito del autor.
2. Anonimiza: quita nombres de autores, título, afiliaciones, número de manuscrito.
3. Revisa que no queden frases que permitan identificar la fuente.
4. Colócalo en `examples/` solo después de la revisión.
