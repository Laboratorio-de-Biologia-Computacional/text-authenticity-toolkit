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

## 2. Redundancia semántica (TF-IDF + cosine similarity)

### ¿Qué es?

Pares de párrafos con similitud coseno sobre vectores TF-IDF (unigramas + bigramas) ≥ `UMBRAL_SIMILITUD_PARRAFOS` (default `0.5`). Detecta:

- **Duplicación literal** (similitud ≈ 1.0) — copy-paste descuidado.
- **Reformulaciones con vocabulario compartido** (similitud 0.5–0.9) — mismo contenido reescrito con sinónimos parciales.

### Por qué importa

Cuando un autor humano escribe, el arco narrativo varía naturalmente entre secciones. Los LLMs, cuando se les pide expandir un documento, tienden a repetir la misma plantilla retórica con datos levemente distintos. La redundancia interna es uno de los indicadores más **objetivos y auditables** de edición descuidada post-generación.

### Por qué TF-IDF y no SequenceMatcher

Una versión anterior usaba `difflib.SequenceMatcher.ratio()`, que compara substrings literales. Esto fallaba ante reformulaciones: dos párrafos que dicen lo mismo con palabras parcialmente distintas daban similitud baja aunque fueran claramente redundantes.

TF-IDF + cosine mide similitud en el espacio de vocabulario ponderado por informatividad: palabras comunes (stop words, conectores) pesan poco; términos técnicos específicos (ej. *PCLS*, *epithelial*, *fibrosis*) pesan mucho. Dos párrafos sobre el mismo tema técnico muestran similitud alta aunque la prosa difiera.

### Umbral configurable

- `UMBRAL_SIMILITUD_PARRAFOS = 0.5` — balance entre sensibilidad y ruido.
- Subir a `0.7` detecta solo duplicación evidente o muy cercana.
- Bajar a `0.3` captura redundancia más sutil pero con más falsos positivos.

### Limitación conocida: redundancia temática pura

TF-IDF premia **vocabulario compartido**. Si el autor repite el mismo tema en múltiples secciones pero con **vocabulario completamente distinto** (ej. una sección usa *PCLS* y *precision-cut lung slices*, otra usa *ex vivo tissue model* y *human-derived lung explants*), la similitud TF-IDF puede ser baja aunque semánticamente hablen de lo mismo.

Esto requeriría **embeddings semánticos** (ej. `sentence-transformers`) que sí capturan sinonimia y paráfrasis. No está implementado aún por tener dependencias pesadas (~100 MB de modelo). Es una mejora planeada para v3.

**Implicación práctica**: si el script reporta 0 pares redundantes pero la lectura humana identifica repetición temática, es un falso negativo legítimo — documenta la redundancia manualmente como evidencia complementaria.

## 3. Verificación de citas vía CrossRef

El toolkit verifica citas en **dos modalidades complementarias**:

### 3a. DOIs explícitos (CrossRef `/works/{doi}`)

Extracción del patrón `10.xxxx/yyyy` en el texto y consulta directa al endpoint de CrossRef por DOI. Verifica:

- Que el DOI **exista** (no sea alucinado por un LLM).
- Que el **año** coincida con el declarado en el texto.
- Que los **autores** coincidan (detecta atribuciones incorrectas tipo "primer autor != senior").
- Que el **título** sea consistente con el tema citado.

### 3b. Citas autor-año (CrossRef search)

Extracción via regex de patrones:

- `(Autor et al., AÑO)` — formato multi-autor más común
- `(Autor & Autor, AÑO)` / `(Autor and Autor, AÑO)` — dos autores
- `(Autor, AÑO)` — autor único
- `Autor et al. (AÑO)` — inline
- `Autor (AÑO)` — inline único

Para cada cita única, se consulta CrossRef search API con:
- `query.author=<apellido>` — filtro por apellido del primer autor citado
- `filter=from-pub-date:AÑO,until-pub-date:AÑO` — ventana exacta del año
- `query.bibliographic=<keywords>` — palabras clave extraídas del párrafo donde aparece la cita, para reducir falsos positivos por homonimia de apellidos

Entre los top 3 candidatos, se elige el primero cuyo primer autor contenga el apellido citado (matching substring, tolerante a CrossRef records inconsistentes tipo `family="Dogyeong Lee"`).

**Interpretación de salida**:
- `[OK ]` — apellido citado coincide con primer autor del paper encontrado.
- `[?? ]` — CrossRef devolvió un paper pero el primer autor no coincide. **Candidato a revisión manual**: puede ser atribución incorrecta del autor del manuscrito, o un falso positivo si el apellido es muy común.
- `[XX ]` — CrossRef no encontró ningún paper con ese autor+año. **Alta probabilidad de cita alucinada**.

### Por qué es la señal más sólida

A diferencia de la densidad estilística (probabilística), **una cita inexistente es un hecho verificable**. Los LLMs alucinan referencias con alta frecuencia, especialmente cuando combinan nombres de autores reales en papers inexistentes, o cambian años.

Esta es la evidencia que recomendamos usar como **columna vertebral** de una evaluación formal — es defensible sin depender de un detector probabilístico.

### Limitaciones

- **CrossRef no cubre todo**: algunas revistas pequeñas, preprints de bioRxiv/medRxiv pre-DOI, libros, tesis, y patentes no están indexadas.
- **Un DOI válido no garantiza cita correcta**: el documento podría citar correctamente un DOI pero atribuirle una afirmación que no aparece en ese paper. Esto requiere lectura humana.
- **Apellidos muy comunes** (*Wang*, *Zhang*, *Smith*) generan `[?? ]` incluso con contexto temático, porque CrossRef devuelve muchos papers plausibles. No asumir automáticamente que `[?? ]` = cita falsa; son **candidatos a revisión manual**.
- **Patrón de alucinación por dominio**: los LLMs tienden a atribuir a autores "canónicos" de un campo (ej. *Selman* en fibrosis pulmonar) papers conceptualmente relacionados aunque no sean de ellos. Vigilar especialmente citas al mismo autor repetidas con años distintos.

## Cómo combinar las señales

Las tres dimensiones son independientes. La evidencia más fuerte viene cuando convergen:

| Caso | Densidad LLM | Redundancia | Citas problemáticas | Veredicto |
|---|---|---|---|---|
| 1 | ALTA | ≥3 pares | >30% fallan/ambiguas | Fuerte indicio de generación por IA |
| 2 | MEDIA | 0-1 pares | <10% fallan | Posible asistencia, revisar manualmente |
| 3 | BAJA | 0 pares | 0% fallan | Consistente con escritura humana |
| 4 | ALTA | 0 pares | 0% fallan | Humano con estilo inflado (posible falso positivo) |
| 5 | BAJA | 0 pares | >30% fallan | Plagio o fabricación intencional de referencias |
| 6 | ALTA | 0 pares (TF-IDF) | >20% fallan | **Patrón típico IPF revisado**: IA con reformulación temática |

El caso 6 es común en reviews generados por LLMs y luego ligeramente editados: el autor humano varía vocabulario para evitar similitud léxica, pero el estilo inflado y las citas alucinadas persisten. Si la lectura humana detecta repetición temática que TF-IDF no captura, documentar manualmente como cuarta señal.

## Qué NO hace este toolkit

- **No da un "porcentaje de IA"** tipo Turnitin/GPTZero.
- **No compara contra bases de datos de plagio** (Turnitin, iThenticate).
- **No detecta paráfrasis sofisticada** (donde el autor reescribió el output del LLM con vocabulario completamente distinto).
- **No captura redundancia puramente temática** con vocabulario disjunto — requiere embeddings semánticos (v3 planeado).
- **No verifica la correspondencia entre cita y afirmación** (una cita puede existir pero el manuscrito atribuirle algo que no dice).
- **No analiza imágenes, tablas ni código** — solo texto.
- **No evalúa calidad científica** (eso requiere lectura humana experta).

Para una evaluación completa, combina este toolkit con:

1. **Turnitin / iThenticate** — plagio tradicional contra bases académicas.
2. **GPTZero / Originality.ai / Grammarly Authorship** — detectores probabilísticos complementarios.
3. **PubMed / Google Scholar** — verificación manual de las citas flaggeadas como `[?? ]` o `[XX ]`.
4. **Lectura humana experta** — lo más importante y no sustituible.
