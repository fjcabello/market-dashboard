# Market Dashboard Constitution

Este proyecto es una tubería de datos desatendida: se ejecuta sola cada día a las
09:00 UTC en GitHub Actions, commitea sus propios resultados y publica en GitHub
Pages. Nadie la está mirando cuando corre. Los principios de abajo están
derivados de ese hecho y de fallos reales observados en el repositorio.

## Core Principles

### I. Publicar degradado antes que no publicar

Un fallo parcial nunca debe impedir la publicación. Si una serie de FRED no
responde, se registra el error y se sigue con las demás. Si un vídeo no tiene
transcript, se salta y se continúa con el canal. Si no hay datos para un panel,
ese panel no se dibuja y el resto de la gráfica sale igual.

Corolario: nada que dependa de un dato opcional puede asumir que existe. Toda
lectura de una columna o fichero opcional se comprueba antes de usarse, y el
HTML no enlaza recursos que no se hayan generado.

### II. Fallar ruidosamente en configuración, silenciosamente en datos

Son dos clases de error distintas y no se tratan igual.

Un secreto ausente o inválido es un fallo de configuración: aborta con código
distinto de cero para que el workflow salga en rojo. Una serie o un vídeo que no
responde es ruido esperable del mundo exterior: se registra y se continúa.

Mezclar ambas categorías es lo que produjo el peor fallo del repositorio: los
workflows reportaron "success" durante 17 días seguidos mientras descargaban
cero transcripts, porque el error de datos se capturaba y el job terminaba en
verde. Un job que no produce ningún dato no debe reportar éxito.

### III. Idempotencia diaria

Ejecutar el proceso dos veces el mismo día no puede corromper nada. Los datos se
vuelven a pedir en origen y se fusionan con lo existente; los ficheros ya
descargados se saltan. Esto es lo que permite relanzar manualmente un día
fallido sin pensárselo.

### IV. Las derivadas se calculan en la frecuencia nativa

Cualquier métrica derivada (interanuales, variaciones, medias) se calcula sobre
la serie en su frecuencia original, antes de reindexar a diario o rellenar
huecos hacia delante.

Es innegociable porque el error no se ve: calcular un interanual después del
ffill diario compara un valor consigo mismo repetido y devuelve un número
plausible pero falso — medido, un 0,25% donde el valor real es 3,04%. Un
gráfico equivocado es peor que un gráfico ausente.

### V. Unidades explícitas por serie, nunca conversiones en bloque

Las series de liquidez se reescalan en bloque a trillones porque comparten
unidad. Todo lo demás (tipos en porcentaje, índices, cuentas) se guarda en su
unidad nativa y va por un canal separado.

No se añaden series nuevas a un grupo que aplica una conversión que no les
corresponde. Un tipo del 4,66% pasado por la conversión de liquidez se convierte
en 0,00000466 sin que salte ningún error.

### VI. La fecha mostrada es la de la observación, no la del índice

Cuando una serie se rellena hacia delante para encajar en un índice diario, hay
que conservar y mostrar la fecha del último dato real. Presentar un dato mensual
como si fuera de hoy es desinformar al lector del dashboard.

## Restricciones técnicas

- Python 3.12 es la referencia: es lo que usa CI. El código debe correr ahí.
- Los secretos (`FRED_API_KEY`, `WEBSHARE_API_KEY`) viven en GitHub Secrets y en
  un `.env` local que nunca se commitea. Ningún secreto entra en el repositorio,
  ni en logs, ni en mensajes de commit.
- Todo secreto que un script necesite debe pasarse explícitamente en el bloque
  `env:` de su step. Un secreto definido en el repositorio pero no pasado al step
  es indistinguible de no tenerlo.
- Las dependencias se declaran en `requirements.txt`. `yfinance` es scraping no
  oficial: no puede estar en un camino crítico sin alternativa.
- Se commitean datos de fuentes públicas (FRED, Treasury, ECB, EIA, FINRA,
  CFTC). No se redistribuyen feeds comerciales de precios.
- El histórico de datos crece a diario. Antes de añadir series en volumen hay que
  considerar el tamaño acumulado del repositorio.

## Flujo de trabajo

- Los workflows corren a diario a las 09:00 UTC y admiten `workflow_dispatch`
  para relanzar o hacer backfill.
- CI commitea y pushea sus propios resultados a la rama por defecto.
- El dashboard se publica desde `docs/`.
- Todo cambio en la tubería se verifica antes de mergear. Cuando no se puede
  probar contra el servicio real por falta de credenciales, se prueba con la
  fuente simulada y se declara explícitamente qué quedó sin verificar.
- Un cambio que produce salida visual se revisa mirando la salida, no solo
  comprobando que el proceso termina sin error.

## Governance

Esta constitución prevalece sobre la costumbre del repositorio. Cuando una
práctica existente la contradiga, gana la constitución y la práctica se corrige.

Toda enmienda se documenta en este fichero con su justificación y sube la
versión. Los principios de arriba están anclados en fallos concretos ya
ocurridos; no se relajan por conveniencia sin argumentar por qué el fallo que
los originó ya no es posible.

Las revisiones verifican el cumplimiento. La complejidad añadida debe estar
justificada frente a la alternativa simple.

**Version**: 1.0.0 | **Ratified**: 2026-08-10 | **Last Amended**: 2026-08-10
