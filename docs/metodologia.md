# Metodología

Este documento explica qué detecta cada módulo del analizador y cómo interpretar los resultados.

## 1. Densidad de marcadores LLM

### ¿Qué es?

Frecuencia (por cada 1000 palabras) de un vocabulario que aparece con densidad anómala en texto generado por modelos de lenguaje (GPT-4, Claude, Gemini, Llama). La lista incluye:

- **Énfasis inflado**: *unprecedented*, *transformative*, *revolutionary*, *paradigm shift*, *pivotal*, *landmark*.
- **Metáforas genéricas**: *bridge the gap*, *cornerstone*, *gold standard*, *seamless integration*, *synergy*.
- **Estructura retórica**: *not merely X but Y*, *it is important to note*, *delve into*, *furthermore*.
- **Adjetivos abstractos**: *intricate*, *multifaceted*, *nuanced*, *robust*, *comprehensive*.

### Interpretación automática

| Densidad (por 1000 palabras) | Interpretación |
|---|---|
| < 3.0 | BAJA — consistente con escritura humana |
| 3.0 – 8.0 | MEDIA — revisar manualmente |
| > 8.0 | ALTA — indicio fuerte de asistencia por LLM |

Estos umbrales son orientativos. En textos biomédicos de review, la densidad suele ser naturalmente más alta que en textos experimentales primarios. Ajusta `UMBRAL_DENSIDAD_ALTA` en el script según tu campo.

### Advertencias importantes

1. **Un humano puede usar estas palabras**. El problema no es la palabra individual sino la **densidad + combinación**.
2. **Falsos positivos en autores no nativos de inglés**. Los escritores ESL tienden a adherirse a fórmulas retóricas que coinciden con las de LLMs.
3. **Falsos negativos en texto editado**. Si el autor reescribió el output del LLM, los marcadores desaparecen pero el razonamiento puede seguir siendo de IA.

## 2. Redundancia interna

### ¿Qué es?

Pares de párrafos con `SequenceMatcher.ratio() >= 0.7` dentro del mismo documento. Indica:

- Secciones duplicadas literalmente (copy-paste descuidado).
- Párrafos muy parecidos donde se "reitera" el mismo contenido con mínimas variaciones (patrón clásico de texto generado y pobremente editado).

### Por qué importa

Cuando un autor humano escribe, el arco narrativo varía naturalmente entre secciones. Los LLMs, cuando se les pide expandir un documento, tienden a repetir la misma plantilla retórica con datos levemente distintos. La redundancia interna es uno de los indicadores más **objetivos y auditables** de edición descuidada post-generación.

### Umbral configurable

- `UMBRAL_SIMILITUD_PARRAFOS = 0.7` — balance entre sensibilidad y ruido.
- Subir a `0.85` reduce falsos positivos (párrafos que simplemente tratan temas relacionados).
- Bajar a `0.5` detecta paráfrasis más sutiles pero con más ruido.

## 3. Verificación de citas vía CrossRef

### ¿Qué es?

Extracción de DOIs del texto (patrón `10.xxxx/yyyy`) y consulta a la API pública de CrossRef para verificar:

- Que el DOI **exista** (no sea alucinado por un LLM).
- Que el **año** coincida con el declarado en el texto.
- Que los **autores** coincidan (detecta atribuciones incorrectas tipo "primer autor != senior").
- Que el **título** sea consistente con el tema citado.

### Por qué es la señal más sólida

A diferencia de la densidad estilística (probabilística), **una cita inexistente es un hecho verificable**. Los LLMs alucinan referencias con alta frecuencia, especialmente cuando combinan nombres de autores reales en papers inexistentes, o cambian años.

Esta es la evidencia que recomendamos usar como **columna vertebral** de una evaluación formal — es defensible sin depender de un detector probabilístico.

### Limitaciones

- **CrossRef no cubre todo**: algunas revistas pequeñas, preprints de bioRxiv/medRxiv pre-DOI, libros, tesis, y patentes no están indexadas.
- **Un DOI válido no garantiza cita correcta**: el documento podría citar correctamente un DOI pero atribuirle una afirmación que no aparece en ese paper. Esto requiere lectura humana.
- **No verifica citas sin DOI**: si el autor cita como "Smith et al., 2024" sin DOI, el script no puede confirmarlo.

## Cómo combinar las tres señales

Cuando las **tres** señales apuntan en la misma dirección, la evidencia es robusta:

| Caso | Densidad | Redundancia | Citas rotas | Veredicto |
|---|---|---|---|---|
| 1 | ALTA | >3 pares | >30% falla | Fuerte indicio de IA |
| 2 | MEDIA | 0-1 pares | <10% falla | Posible asistencia, revisar |
| 3 | BAJA | 0 pares | 0% falla | Consistente con escritura humana |
| 4 | ALTA | 0 pares | 0% falla | Humano con estilo inflado (falso positivo) |
| 5 | BAJA | 0 pares | >30% falla | Plagio o fabricación intencional |

El caso 5 es especialmente importante: indica que el texto puede no haber sido generado por IA pero tiene un problema de integridad distinto (citas fabricadas manualmente).

## Qué NO hace este toolkit

- **No da un "porcentaje de IA"** tipo Turnitin/GPTZero.
- **No compara contra bases de datos de plagio** (Turnitin, iThenticate).
- **No detecta paráfrasis sofisticada** (donde el autor reescribió el output del LLM).
- **No analiza imágenes, tablas ni código** — solo texto.
- **No evalúa calidad científica** (eso requiere lectura humana experta).

Para una evaluación completa, combina este toolkit con:

1. **Turnitin / iThenticate** — plagio tradicional contra bases académicas.
2. **GPTZero / Originality.ai** — detectores probabilísticos complementarios.
3. **Lectura humana experta** — lo más importante y no sustituible.
