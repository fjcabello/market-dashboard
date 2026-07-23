---
name: analyze-transcripts
description: Analiza los transcripts de YouTube de los últimos 15 días (o el rango indicado) y genera una síntesis cruzada en markdown con consensos, discrepancias y temas entre los distintos canales. Úsalo tras correr run_transcripts_cron.sh, o bajo demanda con /analyze-transcripts [dias] o /analyze-transcripts [YYYY-MM-DD] [YYYY-MM-DD].
---

# Analizar transcripts de los últimos N días

Genera una síntesis cruzada (no un resumen independiente por canal) de los transcripts descargados en una ventana de fechas.

## Pasos

1. Determina la ventana de fechas:
   - Sin argumentos: últimos 15 días hasta hoy (inclusive).
   - Un argumento numérico (`/analyze-transcripts 30`): últimos N días hasta hoy.
   - Dos argumentos `YYYY-MM-DD YYYY-MM-DD`: rango explícito (inicio y fin, inclusive).

2. Lista los ficheros en `transcripts/` cuyo nombre empieza por una fecha `YYYY-MM-DD` dentro de esa ventana (ignora `download_transcripts.log` y `cron.log`). Si no hay ninguno, dile al usuario que no hay transcripts en ese rango y no continúes.

3. **Genera o recupera el resumen de cada transcript** (paso clave para no saturar el contexto):
   - Para cada fichero `transcripts/YYYY-MM-DD-Canal.txt`, comprueba si existe `resumenes/YYYY-MM-DD-Canal.md`.
   - Si **existe**: lee solo el resumen (fichero pequeño). No leas el transcript completo.
   - Si **no existe**: lee el transcript completo, extrae un resumen en ≤200 palabras con este formato y guárdalo en `resumenes/YYYY-MM-DD-Canal.md` (crea el directorio si no existe):

     ```markdown
     # YYYY-MM-DD — Canal

     **Tesis principal:** Una o dos frases que capturen el argumento central del vídeo.

     **Puntos clave:**
     - Dato/afirmación 1 (con cifras concretas si las hay)
     - Dato/afirmación 2
     - Dato/afirmación 3
     - (máximo 6 puntos)

     **Activos mencionados:** Lista de tickers, ETFs, materias primas o criptos con precio/target si se dan.

     **Tono:** alcista / bajista / neutro / educativo
     ```

   - El nombre del canal es la parte del filename entre la fecha y `.txt` (quita cualquier sufijo `-<video_id>` si lo hay).

4. Con los resúmenes de todos los ficheros, escribe una síntesis cruzada en markdown. Estructura:

   ```markdown
   # Síntesis YYYY-MM-DD a YYYY-MM-DD

   ## Consensos
   - ...

   ## Discrepancias
   - ...

   ## Temas del periodo
   - ...

   ## Por canal (referencia rápida)
   - **NombreCanal** (N vídeos): evolución/tesis a lo largo del periodo
   ```

   Basa cada punto en lo que realmente dicen los resúmenes — no generalices más allá de lo que el texto sustenta. Si solo hay un canal con transcripts en la ventana, omite "Discrepancias". Si un canal tiene varios vídeos en el periodo, resume su evolución/cambios de opinión, no solo el último vídeo.

5. Guarda el resultado en `conclusiones/YYYY-MM-DD_a_YYYY-MM-DD.md` (crea el directorio `conclusiones/` si no existe).

6. Informa al usuario del path del fichero generado y un resumen de 2-3 líneas de lo más relevante. Menciona cuántos resúmenes nuevos se generaron vs. cuántos ya estaban en caché. No hagas commit/push automáticamente — eso lo decide el usuario en esa sesión.
