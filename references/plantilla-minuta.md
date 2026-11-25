# Plantilla y Estándar de Minuta Ejecutiva de Comisión (~2.5 páginas)

La **Minuta de Comisión** es un documento ejecutivo de síntesis estratégica. Su objetivo es permitir a tomadores de decisión, parlamentarios y directivos comprender con rapidez y profundidad lo ocurrido en una sesión legislativa relevante, sin requerir la lectura de la transcripción completa.

---

## Directrices de Extensión y Estructura

* **Extensión objetivo:** Aproximadamente **2.5 páginas** (alrededor de 1.100 a 1.400 palabras en formato estándar interlineado 1.15).
* **Organización obligatoria en 4 secciones numeradas:**
  1. `I. ANTECEDENTES GENERALES Y OBJETO DE LA SESIÓN`
  2. `II. INTERVENCIONES Y POSICIONES POR EXPOSITOR`
  3. `III. ARTÍCULOS LEÍDOS POR LA SECRETARÍA Y DETALLE DE LAS VOTACIONES`
  4. `IV. RESOLUCIÓN FINAL DE LA SESIÓN`

---

## Formato de Redacción por Sección

### 1. Encabezado Institucional
```markdown
# INFORME Y RESUMEN EJECUTIVO DE LA SESIÓN

**Comisión de [Nombre de la Comisión]**  
**[Cámara de Diputadas y Diputados de Chile / Senado]**  
**Fecha:** [Día de la semana], [DD] de [mes] de [AAAA]  
**Materia:** [Resumen claro del proyecto de ley o asunto puesto en tabla, indicando boletín si corresponde].
```

### 2. Sección I: Antecedentes Generales y Objeto de la Sesión
* Breve párrafo de apertura explicando la convocatoria y si es sesión ordinaria o especial.
* Lista de 3 o 4 ejes sustantivos del proyecto o debate.
* Párrafo institucional indicando quién presidió la sesión, la participación de la secretaría y la presencia de autoridades del Ejecutivo o entidades invitadas.

### 3. Sección II: Intervenciones y Posiciones por Expositor
* Cada expositor debe tener un subtítulo con su nombre completo, cargo y partido político:
  `### 1. Diputado/Senador [Nombre Apellido] ([PARTIDO / Cargo])`
* Bajo cada expositor, utiliza viñetas con título en negrita destacando los 3 o 4 puntos medulares de su postura:
  * `* **[Tema o punto clave]:** [Síntesis de su argumento, objeción o propuesta].`
* Asegúrate de incluir tanto a los parlamentarios como a los representantes del Ejecutivo y gremios relevantes.

### 4. Sección III: Artículos Leídos por la Secretaría y Votaciones
Para cada artículo o indicación sometido a votación:
* Subtítulo: `### [N]. Artículo [X] o Indicación [Y]: [Nombre de la materia]`
* Bloque de cita textual de lo leído por la secretaría:
  ```markdown
  * **Lectura oficial de la Secretaría:**
    > *"Artículo [X].- [Texto íntegro leído por la abogada o abogado secretario]..."*
  ```
* Resultado numérico y proclamación oficial:
  ```markdown
  * **Resultado de la Votación:**
    * **Aprobado por unanimidad:** [X] votos a favor, [Y] en contra, [Z] abstenciones.
    * [Explicación del impacto legal aprobado o si se posterga].
  ```

### 5. Sección IV: Resolución Final y Próximos Pasos
* Párrafo sintético con el cierre formal de la sesión, acuerdos para próximas convocatorias o despacho del proyecto.
* **En minutas de cierre parcial, Sala o Ley de Presupuestos (multi-votación):**
  - Consolidar votaciones en una tabla breve (`Materia | Resultado`) indicando reservas de constitucionalidad (art. 65 inc. 3°) cuando existan.
  - Separar explícitamente:
    - **Confirmado:** partidas, indicaciones o acuerdos efectivamente votados y proclamados.
    - **Anunciado, no confirmado:** compromisos u oficios anunciados por el Ejecutivo o la Mesa sin votación formal.
    - **Pendiente / tramos sin transcripción:** indicaciones sin votación registrada o bloques de audio pendientes. Nunca completar por inferencia lo que no conste en la transcripción.

---

## Criterios Tipográficos para Exportación Word (`.docx`)
* **Tipografía:** Calibri (Títulos 13-17pt, Subtítulos 11-12pt, Cuerpo 10.5pt).
* **Interlineado:** 1.15 con espaciado posterior de 3 a 4 puntos.
* **Paleta de Colores:** Navy Institucional
  - Primario: `#1A365D` (Azul marino profundo para títulos principales).
  - Secundario: `#2B6CB0` (Azul intermedio para subtítulos y bordes de recuadro).
  - Cuerpo: `#2D3748` (Gris carbón oscuro de alta legibilidad).
* **Recuadros de citas:** Borde izquierdo de 3pt color azul `#2B6CB0` con fondo gris muy tenue (`#F7FAFC`) para distinguir nítidamente los textos legales leídos por la secretaría.
