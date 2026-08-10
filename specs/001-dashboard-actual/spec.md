# Feature Specification: Dashboard de liquidez, macro y transcripts

**Feature Branch**: `001-dashboard-actual`
**Created**: 2026-08-10
**Status**: Baseline — especificación inferida del código existente
**Input**: Ingeniería inversa del repositorio a fecha 2026-08-10, no una funcionalidad nueva

Este documento describe lo que el sistema **hace hoy**, para que futuras
funcionalidades tengan una línea base contra la que planificar. Donde el
comportamiento actual es defectuoso, se marca como tal en vez de describirse
como intencionado.

## User Scenarios & Testing *(mandatory)*

El usuario es un inversor particular que sigue la liquidez global y a un conjunto
de comentaristas de mercado, y quiere una foto diaria sin dedicarle tiempo.

### User Story 1 - Ver el estado de la liquidez y los mercados (Priority: P1)

Como inversor, quiero abrir una página y ver en qué punto está la liquidez neta
del sistema y cómo se han movido los grandes activos, sin ejecutar nada.

**Why this priority**: Es la razón de existir del repositorio. Sin esto, nada más
tiene sentido.

**Independent Test**: Abrir la página publicada y comprobar que muestra un dato
del día hábil más reciente.

**Acceptance Scenarios**:

1. **Given** el proceso diario se ejecutó correctamente, **When** el usuario abre
   el dashboard, **Then** ve la liquidez neta, M2, los repos inversos y los
   precios de S&P 500, MSCI World, oro y Bitcoin, con la fecha de actualización.
2. **Given** el usuario quiere detalle reciente, **When** cambia a la pestaña de
   3 meses, **Then** ve los mismos paneles con mayor resolución temporal.
3. **Given** una fuente de precios falló, **When** se genera la página, **Then**
   los activos disponibles se muestran igual y los ausentes se omiten.

### User Story 2 - Situar el contexto macro (Priority: P2)

Como inversor, quiero ver la curva de tipos, la inflación, el empleo, el dólar y
los diferenciales de crédito, porque son las variables que explican los
movimientos de los activos que sigo.

**Why this priority**: Sin esto el dashboard muestra el qué pero no el porqué.
Se añadió después de comprobar que un análisis del periodo no podía apoyarse en
ninguna de estas variables.

**Independent Test**: Abrir la pestaña Macro y verificar que cada panel muestra
su última observación con su fecha real.

**Acceptance Scenarios**:

1. **Given** FRED devolvió las series, **When** el usuario abre la pestaña Macro,
   **Then** ve cinco paneles: curva de tipos con el diferencial 10Y-2Y,
   inflación contra el objetivo del 2%, nóminas y paro, dólar y dólar-yen, y
   diferencial high yield con crudo.
2. **Given** una serie mensual se rellenó hacia delante, **When** se muestra su
   valor, **Then** la fecha indicada es la de la observación real y no la de hoy.
3. **Given** FRED no devolvió ninguna serie macro, **When** se genera la página,
   **Then** la pestaña Macro no aparece y no se enlaza ninguna imagen inexistente.

### User Story 3 - Seguir a los comentaristas sin verlos (Priority: P2)

Como inversor, quiero que se descarguen los transcripts de los canales que sigo y
poder pedir una síntesis cruzada de un periodo, para saber en qué coinciden y en
qué discrepan sin ver horas de vídeo.

**Why this priority**: Es el diferencial del repositorio frente a cualquier
dashboard de liquidez. Va después de P1 porque depende de una fuente externa
frágil.

**Independent Test**: Ejecutar la descarga y comprobar que aparecen ficheros
nuevos con la convención de nombre; después pedir una síntesis de un rango y
comprobar que se genera el fichero de conclusiones.

**Acceptance Scenarios**:

1. **Given** un canal publicó un vídeo con subtítulos, **When** corre la
   descarga, **Then** se guarda `transcripts/YYYY-MM-DD-Canal.txt` en texto plano
   sin marcas de tiempo.
2. **Given** el transcript de ese día ya existe, **When** vuelve a correr,
   **Then** se salta sin volver a descargarlo.
3. **Given** hay transcripts en un rango, **When** se pide la síntesis, **Then**
   se genera un resumen por vídeo reutilizando los ya cacheados y un documento
   con consensos, discrepancias, temas y evolución por canal.

### Edge Cases

- **Una serie de FRED no responde**: se registra y las demás continúan.
- **Todas las series macro fallan**: el dashboard sale sin pestaña Macro.
- **El proveedor de proxy rechaza la conexión**: hoy se registran 27 errores por
  ejecución y el job termina en verde. Es un defecto conocido, no el
  comportamiento deseado (ver Success Criteria SC-005).
- **Dos vídeos del mismo canal el mismo día**: el segundo se guarda con sufijo
  de identificador de vídeo.
- **Un canal sin subtítulos disponibles**: se cuenta como omitido, no como error.
- **El proceso corre dos veces el mismo día**: no duplica ni corrompe datos.
- **Un rango sin transcripts**: se informa y no se genera síntesis vacía.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE descargar diariamente las series de liquidez de
  FRED y calcular la liquidez neta como balance de la Fed menos TGA menos repos
  inversos.
- **FR-002**: El sistema DEBE descargar los precios de referencia configurados y
  tolerar la ausencia de cualquiera de ellos.
- **FR-003**: El sistema DEBE descargar las series macro de tipos, inflación,
  empleo, divisas, crédito y crudo, conservándolas en su unidad nativa.
- **FR-004**: El sistema DEBE calcular las métricas derivadas sobre la frecuencia
  original de cada serie, antes de reindexar a diario.
- **FR-005**: El sistema DEBE registrar la fecha de la última observación real de
  cada serie y usarla al presentarla.
- **FR-006**: El sistema DEBE acumular el histórico en disco fusionando lo nuevo
  con lo existente, sin perder columnas ya presentes.
- **FR-007**: El sistema DEBE generar las gráficas y una página estática, y
  omitir los elementos cuyos datos falten.
- **FR-008**: El sistema DEBE descargar los transcripts de los canales
  configurados, revisando los N vídeos más recientes de cada uno.
- **FR-009**: El sistema DEBE saltar los transcripts ya descargados.
- **FR-010**: El sistema DEBE permitir un backfill puntual ampliando el número de
  vídeos revisados por canal.
- **FR-011**: El sistema DEBE abortar con código de error si un secreto requerido
  falta o es inválido.
- **FR-012**: El sistema DEBE continuar tras el fallo de una serie o un vídeo
  concretos, dejando constancia en el log.
- **FR-013**: El sistema DEBE poder producir, bajo demanda, una síntesis cruzada
  de un rango de fechas, cacheando el resumen individual de cada transcript.

### Key Entities

- **Serie de liquidez**: identificador de FRED, unidad de origen y factor de
  conversión a trillones.
- **Serie macro**: identificador de FRED, etiqueta, unidad nativa y frecuencia
  (diaria, semanal, mensual).
- **Histórico**: tabla indexada por fecha con una columna por serie y por precio.
- **Canal**: nombre, URL, idioma y estilo.
- **Transcript**: fichero de texto identificado por fecha y canal.
- **Resumen**: tesis principal, puntos clave, activos mencionados y tono, por
  transcript.
- **Síntesis**: consensos, discrepancias, temas del periodo y evolución por canal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El dashboard refleja el dato del último día hábil disponible tras
  cada ejecución diaria.
- **SC-002**: Un fallo en cualquier serie individual no impide la publicación del
  resto.
- **SC-003**: Ninguna métrica derivada se calcula sobre datos rellenados hacia
  delante.
- **SC-004**: Ningún dato se presenta con una fecha posterior a su observación
  real.
- **SC-005**: Una ejecución que no produce ningún dato no reporta éxito.
  **Actualmente no se cumple**: la descarga de transcripts lleva desde
  2026-07-24 terminando en verde con cero descargas.
- **SC-006**: Relanzar el proceso el mismo día no altera el resultado.

## Assumptions

- FRED es la fuente de referencia y su clave está disponible como secreto.
- Las descargas de transcripts dependen de un proxy porque YouTube bloquea las
  IP de los runners de CI; esa dependencia es hoy el punto más frágil del
  sistema.
- Los canales seguidos son comentaristas, no fuentes de datos: la síntesis
  documenta lo que dicen, no valida si aciertan.
- El repositorio es de un solo usuario y no requiere control de acceso.

## Deuda conocida

Registrada aquí para que las funcionalidades futuras no la den por resuelta:

1. **Sin verificación previa al merge**: ningún workflow se dispara con
   `pull_request`, así que nada comprueba los cambios antes de entrar en la rama
   principal.
2. **Descarga de transcripts caída** desde 2026-07-24 por rechazo del túnel del
   proxy, reportando éxito (SC-005).
3. **`plot` y `plot_zoom` están casi duplicadas**, con la ventana temporal como
   única diferencia real.
4. **`yfinance` en camino crítico** para cuatro precios, sin alternativa.
5. **El histórico crece en cada ejecución** y se commitea completo.
