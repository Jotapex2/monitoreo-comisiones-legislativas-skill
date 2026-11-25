# Plantilla y Estándar de Informe de Comisión (Formato Institucional)

El **Informe de Comisión** es el registro sustantivo, cronológico y exhaustivo de una sesión legislativa, diseñado siguiendo el estándar institucional del Congreso Nacional de Chile (Senado y Cámara de Diputadas y Diputados).

A diferencia de la Minuta Ejecutiva (que es un resumen analítico de 2.5 páginas), el Informe de Comisión no tiene límite artificial de extensión: debe registrar con detalle las intervenciones, exposiciones técnicas, debates y votaciones.

---

## Estructura Institucional Estándar

```
[Encabezado: Comisión, Cámara, Fecha]
[Orden del día con Boletines e Invitados]
[Asistentes: Parlamentarios con Partido y Cargo, Ejecutivo, Invitados]
[Primer Punto en Tabla / Segundo Punto en Tabla...]
    ├── [Exposiciones de Invitados / Autoridades]
    ├── [Debate Parlamentario Cronológico con Apellido (Partido)]
    └── [Indicaciones y Votaciones con conteo exacto]
[Estado de Despacho / Cierre de la Sesión]
```

---

## Formato de Redacción por Sección

### 1. Encabezado
```markdown
# Comisión de [Nombre de la Comisión]
**[Senado / Cámara de Diputadas y Diputados]**  
[DD] de [mes] del [AAAA]
```
*(En Word: Título de Comisión en 14pt negrita, Cámara en 14pt negrita, Fecha en texto normal).*

### 2. Orden del día
Se listan los proyectos de ley o materias en tabla. Si es proyecto de ley, debe incluir el número de boletín legislativo oficial:
```markdown
**Orden del día**
* 1.- (Bol. N° [XXXXX-XX]) con el objeto de [descripción oficial del proyecto de ley o materia a tratar].
* 2.- Analizar [materia o situación de fiscalización], con asistencia de [invitados formalmente convocados].
```

### 3. Asistentes
Lista detallada de todos los presentes en la sala o conectados telemáticamente:
```markdown
**Asistentes:**
* [Nombre Completo], presidente/a ([PARTIDO])
* [Nombre Completo] ([PARTIDO])
* [Nombre Completo] ([PARTIDO])
* [Detalle de reemplazos: Diputado/a [Nombre] en reemplazo de [Nombre]]
* [Nombre Completo], [Cargo de Autoridad del Ejecutivo]
* [Nombre Completo], [Cargo de Invitado / Gremio / Organización]
* [Nombre Completo], abogado/a secretario/a de la comisión
```

### 4. Puntos en Tabla y Desarrollo
Cuando la sesión trata varios temas, se divide formalmente:
```markdown
## Primer Punto en Tabla: [Descripción breve de la materia o Boletín]

### Exposiciones
**[Nombre y Apellido], [Cargo del Expositor]:**  
[Relato directo en **primera persona** (estilo transcripción editada), incluyendo cifras, fundamentos de derecho o diagnósticos presentados ante la comisión].

### Debate
**[Apellido o Nombre] ([PARTIDO]):**  
[Intervención en **primera persona** (estilo transcripción editada), con preguntas a los expositores, críticas políticas o respaldo a la iniciativa].

**[Nombre Expositor / Autoridad]:**  
[Respuesta detallada en **primera persona** dada por el expositor ante las consultas parlamentarias].
```

### 5. Indicaciones y Votaciones
Cada indicación o votación de artículo debe quedar registrada con su identificación, texto o materia y resultado numérico:
```markdown
**Indicación [N° o Letra]:**  
[Texto o descripción de la indicación sometida a voto].

[Discusión previa sobre admisibilidad reglamentaria o quórum, si la hubo].

**Se vota [materia o indicación]:**  
[X] votos a favor, [Y] en contra, [Z] abstenciones. Aprobado por unanimidad. / Aprobada la indicación [N°]. / Se rechaza.
```

### 6. Cierre Institucional
Registra formalmente el estado final del trámite legislativo:
```markdown
**El proyecto es despachado de la comisión.**  
*(o bien: "Habiéndose cumplido el objeto de la sesión, se levanta.")*
```

---

## Criterios Tipográficos para Exportación Word (`.docx`)
* **Fuente:** Arial o Calibri 11pt para el cuerpo de texto.
* **Títulos principales:** 14pt en negrita.
* **Subtítulos y nombres de expositores:** 11pt en negrita.
* **Párrafos de oradores:** Nombre y partido en negrita (`Diputado Longton (RN):`), seguido del texto con sangría o párrafo independiente.
* **Votaciones:** Párrafo en negrita destacando el resultado para facilitar la búsqueda visual rápida en el documento.

---

## Variante: Informe de Sesión de Sala (Cámara o Senado)

Cuando el seguimiento corresponde a una **Sesión de Sala** (pleno) sobre un proyecto específico o punto en tabla, usar la siguiente estructura ampliada (compatible con `create_informe_document` en `scripts/generate_commission_docs.py`):

1. **Encabezado de Sala:**
   - Cámara y Legislatura (`374° Legislatura`), Sesión de Sala N°, Fecha.
   - Boletín N°, Trámite Constitucional y Reglamentario, Urgencia (con Mensaje N°), Fuente de transmisión y Estado final de despacho.
2. **I. Autoridades del Ejecutivo Presentes:** Nombre completo y cartera (Ministros/as, Ministros/as subrogantes, Subsecretarios/as).
3. **II. Informes de Comisiones Técnicas:**
   - Diputados/Senadores informantes de cada comisión (ej. Constitución, Hacienda) con partido, distrito/circunscripción, marca horaria, contenido aprobado, votaciones en comisión e Informes Financieros DIPRES.
4. **III. Resumen de Intervenciones en Sala (Debate Parlamentario):**
   - Lista numerada cronológicamente con todos los parlamentarios que intervinieron:
     `N. Dip./Sen. [Nombre Completo] ([PARTIDO]) — Distrito/Circunscripción X, Región Y (HH:MM:SS – HH:MM:SS)`
   - Síntesis de argumentos sustantivos + línea explícita `Posición:` (a favor, en contra, solicitudes de votación separada).
5. **IV. Intervención de Cierre del Ejecutivo:** Individualizada por autoridad con compromisos, plazos y respuestas técnicas.
6. **V. Votaciones y Despacho:**
   - Votación en general (quórum aplicable y resultado exacto) + cada **votación separada** (artículo/numeral, solicitantes y resultado numérico) + efecto jurídico del despacho (promulgación, tercer trámite o comisión mixta).
