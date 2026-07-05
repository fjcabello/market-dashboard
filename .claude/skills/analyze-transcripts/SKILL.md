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
3. Lee el contenido de cada fichero encontrado. El nombre del canal es la parte del filename entre la fecha y `.txt` (quita cualquier sufijo `-<video_id>` si lo hay). Agrupa mentalmente por canal y ordena por fecha.
4. Con esos textos, escribe una síntesis en markdown que cruce lo que dicen los canales en esa ventana — no un resumen independiente por vídeo. Estructura sugerida:

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

   Basa cada punto en lo que realmente dicen los transcripts — no generalices más allá de lo que el texto sustenta. Si solo hay un canal con transcripts en la ventana, omite "Discrepancias" (no hay nada que cruzar). Si un canal tiene varios vídeos en el periodo, resume su evolución/cambios de opinión, no solo el último vídeo.
5. Guarda el resultado en `conclusiones/YYYY-MM-DD_a_YYYY-MM-DD.md` (fechas de inicio y fin de la ventana; crea el directorio `conclusiones/` si no existe).
6. Informa al usuario del path del fichero generado y un resumen de 2-3 líneas de lo más relevante. No hagas commit/push automáticamente — eso lo decide el usuario en esa sesión.
