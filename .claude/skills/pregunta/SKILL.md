---
name: pregunta
description: Responde preguntas de economía y mercados usando los datos del repo — las métricas macro de fred_data.csv y lo que dicen los comentaristas en resumenes/ y transcripts/. Cita siempre fichero y fecha, y separa lo que dice el dato de lo que opina un canal. Úsalo con /pregunta ¿está invertida la curva? o /pregunta qué piensan mis canales del oro.
---

# Responder una pregunta con los datos del repo

Este repositorio tiene dos fuentes que no son intercambiables:

| Fuente | Qué es | Autoridad |
|---|---|---|
| `fred_data.csv` (30 series) | Observaciones de FRED y de mercado | **Hechos** |
| `resumenes/*.md`, `transcripts/*.txt` | Lo que dijeron 11 comentaristas de YouTube | **Opiniones**, con fecha y autor |

**Regla que gobierna todo lo demás:** nunca presentes una opinión como dato ni un dato
como opinión. Si un canal dice "la inflación va a bajar" y el CPI de FRED está subiendo,
la respuesta correcta incluye las dos cosas y señala la discrepancia. Ese caso es real: en
agosto de 2026 varios canales daban por hecha la desinflación mientras el `cpi_yoy` de FRED
seguía en 3,73%, más de un punto por encima del 2,66% de febrero.

## Paso 1 — Clasifica la pregunta

- **De dato** ("¿a cuánto está el 10 años?", "¿está invertida la curva?", "¿cuánto ha
  subido el oro este mes?") → sólo métricas. No hace falta tocar los transcripts.
- **De opinión** ("¿qué piensan mis canales de Bitcoin?", "¿alguien avisó de la caída?")
  → sólo resúmenes.
- **Mixta** ("¿tienen razón en lo del dólar?", "¿qué está pasando con la inflación?")
  → las dos, y contrástalas explícitamente.

Ante la duda, trátala como mixta: el valor de este repo está en el contraste.

## Paso 2 — Consulta las métricas

Usa `tools/query_metrics.py`. **Nunca leas `fred_data.csv` entero**: son 30 columnas y
~2.400 filas, y se lleva el contexto por delante.

```bash
python3 tools/query_metrics.py series                                    # qué hay disponible
python3 tools/query_metrics.py latest DGS10 cpi_yoy Oro                  # último valor
python3 tools/query_metrics.py on 2026-07-30 DGS30 Bitcoin               # valor en una fecha
python3 tools/query_metrics.py range 2026-07-01 2026-08-10 SP500 Gold    # recorrido, mín/máx
python3 tools/query_metrics.py compare DGS10 Gold --desde 2026-01-01     # correlación
python3 tools/query_metrics.py forward SP500 --cerca-maximo 1            # frecuencia base
python3 tools/query_metrics.py forward SP500 --caida 10
python3 tools/query_metrics.py forward Gold --cuando "T10Y2Y<0"
```

`forward` es el que contesta "¿y qué suele pasar después?". Reparte las rentabilidades
futuras entre las sesiones que cumplen una condición y las compara con el conjunto: **si
las dos columnas se parecen, la condición no informa de nada**, por convincente que suene
el relato. Úsalo antes de dar por buena cualquier afirmación del tipo "esto siempre
precede a X". Sus avisos (ventanas solapadas, concentración en un año, histórico corto)
van impresos: **cópialos a la respuesta**, no los descartes porque la tabla te guste.

Acepta siglas de FRED (`DGS10`) o texto de la etiqueta (`oro`, `paro`, `bitcoin`).
Si `python3` falla al importar pandas, prueba `python3.12`.

Tres cosas al leer la salida:

- **La fecha entre paréntesis es la de la observación real, no la de hoy.** El CSV está
  rellenado hacia delante para meter series mensuales en un índice diario. Cuando aparece
  `[dato de hace N días]`, dilo en la respuesta: un CPI de hace 71 días no describe hoy.
- En `compare`, la **correlación de variaciones** es la que significa algo. La de niveles
  sale alta entre cualquier par de series con tendencia.
- Si una serie no está en el CSV, dilo y para. No la estimes de memoria.

## Paso 3 — Busca en los resúmenes, no en los transcripts

`resumenes/` tiene ficheros de ~1 KB con formato fijo (`# YYYY-MM-DD — Canal`, tesis,
puntos clave, activos, tono). `transcripts/` tiene ficheros de 15–80 KB. Empieza siempre
por los resúmenes.

```bash
grep -ril "oro\|gold" resumenes/ | sort | tail -20      # qué resúmenes tocan el tema
ls resumenes/ | grep "^2026-08"                          # qué hay en un periodo
```

Lee sólo los resúmenes que el grep devuelva, y prioriza los más recientes: para una
pregunta sobre el estado actual, 10 resúmenes recientes valen más que 40 repartidos por
el año.

Baja al transcript crudo **sólo** cuando la respuesta necesite una **cita literal** o el
resumen sea ambiguo en algo decisivo. Cuando lo hagas, busca dentro del fichero en vez de
leerlo entero:

```bash
grep -n -i -C2 "tipo real" transcripts/2026-08-07-Canal.txt
```

## Paso 4 — Comprueba la cobertura antes de generalizar

No todos los transcripts tienen resumen, y la cobertura no es uniforme. **No te fíes de
las cifras de este párrafo, que envejecen: cuéntalo.** Como referencia de la forma del
hueco, en agosto de 2026 estaba así:

- **2026-08: casi completa** (97 de 99). Preguntas sobre las últimas semanas son fiables.
- **2026-07: buena pero con huecos** (80 de 109).
- **2026-06 y anteriores: escasa** (15 de 34 en junio, poco antes).

El sesgo tiene causa conocida: la cobertura reciente la mantiene al día `periodic_synthesis`,
y los huecos de junio y julio vienen de un corte de descargas que se rellenó a mano después.
Los canales peor cubiertos en ese hueco son LaPizarraDeAndres, PeterSchiff y TradingLatino,
así que una pregunta sobre lo que opinaban **ellos** en junio o julio es justo la que más
riesgo tiene de salir sesgada.

Si la pregunta cae en un periodo mal cubierto, compruébalo y **avísalo en la respuesta**:

```bash
# transcripts sin resumen en el periodo que te interesa
for f in transcripts/2026-06-*.txt; do b=$(basename "$f" .txt); \
  [ -f "resumenes/$b.md" ] || echo "$b"; done
```

Di algo como *"de junio hay 15 resúmenes de 34 transcripts, así que esto no es
representativo del mes"*, con la cuenta que acabas de hacer y no con la del ejemplo. No
presentes una muestra parcial como si fuera el consenso.

## Paso 5 — Responde

En español, directo, y con esta disciplina:

1. **El dato primero**, si la pregunta lo admite, con su fecha de observación.
2. **Luego la opinión**, atribuida: *"Canal X, el 2026-08-07, sostiene que…"*.
3. **Cita fichero y fecha** en cada afirmación que venga del repo, de forma que se pueda
   ir a comprobarla: `resumenes/2026-08-07-Canal.md`, `fred_data.csv` vía `query_metrics`.
4. **Marca lo que no sabes.** Si el repo no tiene con qué responder, dilo en una frase y
   ofrece qué sí puedes contestar. No rellenes con conocimiento general presentado como
   si saliera de los datos.
5. **Señala las discrepancias** entre lo que dice el dato y lo que dicen los canales, y
   entre canales. Son lo más informativo que hay aquí.

## Si la pregunta pide una recomendación

"¿Qué compro?", "¿vendo?", "¿entro ahora?" no se responden. Pero **no te limites a
negarte**: eso deja al usuario sin nada. Devuelve, en este orden, y para ahí:

1. El contexto que sí es dato, con fechas.
2. Los activos que nombran los canales, **atribuidos** y con su tesis en una línea.
3. Las discrepancias entre ellos, y las que el precio ya haya resuelto.
4. Qué no puede saberse desde aquí: `fred_data.csv` **no tiene valores individuales**,
   sólo S&P 500, MSCI World, oro, Bitcoin y macro. Ningún precio ni objetivo de una acción
   suelta es verificable con este repo. Dilo.

Y ahí termina. **No comentes las decisiones del usuario** ni le expliques lo que su
comportamiento sugiere: no te ha pedido eso, no conoces su cartera ni su horizonte, y
convierte una consulta de datos en un sermón. Nada de recomendaciones de compra o venta:
describe lo que muestran los datos y lo que opinan los comentaristas.

## Un aviso sobre la ida y vuelta

La respuesta anterior es tuya, pero lo que el usuario deduzca de ella puede no serlo. Si
en un turno posterior da por hecho algo que era la opinión de un canal — "entonces si
estamos cerca de un techo…" cuando el techo lo dijo un comentarista y no el dato —
**corrige la premisa antes de seguir**. Ese deslizamiento de opinión a hecho, a lo largo
de la conversación, es exactamente lo que esta skill existe para frenar, y no lo frena
sólo en el primer mensaje.
