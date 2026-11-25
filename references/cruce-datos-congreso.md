# Guía de Cruce y Validación con el MCP datos-congreso

El servidor MCP **`datos-congreso`** proporciona acceso directo y estructurado a los registros de la Cámara de Diputadas y Diputados y del Senado de Chile.

Durante el monitoreo de comisiones, este MCP debe utilizarse para asegurar la máxima precisión jurídica y parlamentaria, evitando errores en nombres, partidos políticos, números de boletín y estados de tramitación.

---

## 1. Verificación de Parlamentarios y Filiación Política

### Herramienta: `search_politicians` / `get_politician_by_id`
Cuando un parlamentario interviene en la sesión o figura en la lista de asistencia:
1. Llama a `search_politicians` con el apellido o nombre (ej. `query: "Manouchehri"`, `query: "Ross"`, `query: "Vodanovic"`).
2. Obtén la información oficial:
   - Nombre legal completo (ej. `Daniel Manouchehri Lobos`).
   - Cámara de pertenencia (`diputado` / `senador`).
   - Partido político oficial y sigla:
     * `PS` = Partido Socialista
     * `RN` = Renovación Nacional
     * `UDI` = Unión Demócrata Independiente
     * `PC` = Partido Comunista
     * `REP` = Partido Republicano
     * `PL` = Partido Liberal
     * `PDG` = Partido de la Gente
     * `FA` = Frente Amplio
     * `PNL` = Partido Nacional Libertario
     * `PR` = Partido Radical
     * `PPD` = Partido por la Democracia
     * `DC` = Democracia Cristiana
     * `EVOP` = Evópoli
     * `IND` / `Ind.` = Independiente (indicar si va en bancada cuando corresponda, ej. `IND-PPD` o `IND-RN`).
3. Formato obligatorio en el documento:
   - En Comisiones: `Diputado [Nombre Apellido] ([SIGLA])` o `Senador [Nombre Apellido] ([SIGLA])`.
   - En Sesiones de Sala: agregar distrito/circunscripción y región para trazabilidad territorial, ej. `Dip. Raúl Leiva Carvajal (PS) — Distrito 14, Región Metropolitana`.
4. **Cruce visual con chyrons:** Cuando el audio no anuncie claramente el nombre del orador o el Whisper deforme un apellido (ej. *"Esquella"*, *"Huacán"*), contrastar el fotograma (`scripts/grab_chyrons.py`) con `search_politicians` antes de consolidar el nombre en el informe. Si no es verificable, explicitar tal cual apareció en la transcripción sin inventar el nombre ni el partido.

---

## 2. Verificación de Boletines Legislativos y Tramitaciones

### Herramienta: `get_bill_by_id` / `search_bills`
1. Cuando se mencione un boletín en la sesión (ej. `Bol. N° 18623-07` o `16854-19`):
   - Ejecuta `get_bill_by_id` con el ID o número de boletín.
   - Extrae el título oficial exacto del proyecto de ley.
   - Extrae los parlamentarios autores de la moción o si es de origen en Mensaje Presidencial.
   - Identifica si el proyecto es una moción individual o un **proyecto refundido** (fusión de varios boletines).
2. Herramienta `list_tramitaciones`:
   - Permite conocer la urgencia vigente (Simple, Suma o Discusión Inmediata) y la comisión en que se encuentra radicado el proyecto.

---

## 3. Validación de Votaciones y Asistencia

### Herramientas: `list_bill_votes` y `get_attendance`
- Al finalizar la sesión, permite contrastar si el acta formal del Congreso coincide con el cómputo registrado durante la transmisión en vivo, garantizando trazabilidad absoluta.
