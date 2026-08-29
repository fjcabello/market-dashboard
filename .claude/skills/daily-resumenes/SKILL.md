---
name: daily-resumenes
description: Compara transcripts/ contra resumenes/ y escribe, con el mismo nivel de detalle y formato que los resúmenes existentes, los que falten. Sin síntesis cruzada (para eso está /analyze-transcripts). Pensado para ejecutarse a diario en CI justo después de la descarga de transcripts. Uso bajo demanda: /daily-resumenes.
---

# Generar los resúmenes de transcripts que falten

Este skill no genera ninguna síntesis cruzada — solo mantiene al día `resumenes/`, un fichero por transcript, con el detalle que ya tienen los existentes. La síntesis cruzada periódica en `conclusiones/` la genera por separado la skill `/analyze-transcripts`.

## Pasos

1. Lista los nombres base (sin extensión) de `transcripts/*.txt` y de `resumenes/*.md`. Calcula la diferencia: qué transcripts no tienen resumen todavía.

2. Si no falta ninguno, dilo brevemente y termina. No toques nada más.

3. Si falta alguno, antes de escribir lee 2-3 resúmenes existentes recientes (ordena `resumenes/` por fecha de modificación y coge los últimos) para calibrar formato y profundidad. **Son resúmenes largos y ricos en cifras concretas, no de 200 palabras.** Estructura:

   ```markdown
   # YYYY-MM-DD — Canal

   **Tesis principal:** 2-4 frases con el argumento central del vídeo.

   **Puntos clave:**
   - Subsecciones en negrita por tema, con cifras y niveles concretos, y citas o argumentos textuales del comentarista cuando aporten
   - (todos los que hagan falta — no hay límite artificial de puntos)

   **Activos mencionados:** tickers/activos con los niveles o precios objetivo que se dieron.

   **Tono:** alcista / bajista / neutro, con matices.
   ```

   Reglas que se han seguido en todos los resúmenes existentes y que hay que mantener:

   - **Vídeo sin contenido de mercado** (tutorial fiscal, clase técnica sin tesis, biografía, clip corto sin sustancia): dilo explícitamente en la primera línea, con un puntero a otro vídeo del mismo canal que sí tenga contenido de mercado. No fuerces un resumen largo artificial en esos casos — uno corto y honesto es mejor.
   - **Cifra dudosa o comentarista que se contradice dentro del propio vídeo:** señálalo explícitamente en el resumen en vez de arreglarlo adivinando cuál sería la cifra "correcta".
   - **Posición propia o conflicto de interés declarado por el comentarista:** hazlo constar siempre.
   - **Vídeo que conecta con otro del mismo canal en fechas cercanas** (una previsión que se cumple, se contradice o se matiza al día siguiente): añade una nota cruzada breve en ambos ficheros, citando la fecha del otro resumen.
   - Nunca opines tú sobre si el comentarista acierta o se equivoca — solo reporta lo que dice y, cuando proceda, contrástalo con datos o con otro comentarista del corpus.

4. Para cada transcript que falte, lee el fichero completo. Si es muy largo (varios cientos de líneas, típico en streamings de trading), usa `grep`/`sed -n` para localizar primero las secciones con sustancia (menciones de activos, cifras, nombres propios) en vez de leerlo entero de una sentada sin criterio.

5. Escribe cada resumen en `resumenes/YYYY-MM-DD-Canal.md` (el nombre de canal es la parte del fichero de transcript entre la fecha y `.txt`).

6. Al terminar, informa de cuántos resúmenes nuevos se generaron y de la cobertura final (`transcripts/` vs `resumenes/`). **No hagas commit ni push** — eso lo decide quien invoque el skill; en CI, el propio workflow se encarga después de que termines.
