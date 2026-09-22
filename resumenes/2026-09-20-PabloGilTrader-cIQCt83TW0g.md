# 2026-09-20 — PabloGilTrader

**Vídeo:** "Bitcoin: ¿fin del criptoinvierno o falsa señal?" (youtu.be/cIQCt83TW0g) — no capturado por el pipeline automático ese día porque ya existía `2026-09-20-PabloGilTrader.txt` (el clip de interés compuesto); ver nota de bug más abajo.

**Tesis principal:** Señales mixtas, sin cerrar el pronóstico. Reconoce los primeros síntomas de que el criptoinvierno podría estar terminando, pero insiste en que aún faltan confirmaciones clave a nivel semanal y en el análisis relativo frente a otros activos.

**Puntos clave:**

**Repaso del marco temporal (modelo del halving):**
- Su previsión de meses atrás situaba el fin del criptoinvierno entre octubre y noviembre de 2026; seguimos dentro de ese plazo
- Bitcoin no corrigió tanto como esperaba (preveía -72%, se quedó en algo más de -50%) y los indicadores (RSI, estocástico) no llegaron a niveles de sobreventa típicos del final de ciclos anteriores

**Patrón de confirmación (basado en los criptoinviernos de 2015, 2018 y 2022):**
- Necesita ver máximos y mínimos crecientes, confirmados solo cuando el precio rompe el máximo anterior — no basta un simple rebote

**Su propia gestión de riesgo:**
- Vendió Bitcoin al perder los 105.000; su plan de recompra en 35.000-40.000 nunca se cumplió
- Recompró al romper 67.000, pero solo la mitad de la posición que había vendido, dejando el resto condicionado a más confirmación

**Niveles clave:**
- Bitcoin: 67.000 ya superado (positivo); 83.000 (máximo anterior) todavía sin cierre semanal por encima
- Ethereum: rompió 1.850 (doble suelo activado); no confirma cierre semanal claro sobre 2.450
- Solana: completó un doble suelo, objetivo potencial 150
- Ripple: no rompió su zona de techo 12-18 (vigente desde 2021)
- Cardano: más débil, perdió soporte y no lo ha recuperado

**Análisis relativo (lo que más le falta confirmar):**
- Ni Ethereum, ni Solana, ni Ripple están haciendo mejor que Bitcoin todavía — señal que él considera necesaria para dar por iniciado un ciclo alcista
- Tampoco ve ruptura clara en los relativos Bitcoin/Nasdaq ni Bitcoin/oro, aunque dice que "se ha avanzado mucho" y falta poco

**Objetivos de precio a 4 años (dos modelos, no predicciones cerradas):**
- Power Law (relación histórica precio-tiempo): rango 279.000-837.000, centro ~481.000
- Modelo "River" (estimación de entrada de dinero institucional): rango 250.000-840.000

**Cierre:** remarca que son modelos, no certezas; dice ajustar constantemente su visión según los datos y que la responsabilidad de cualquier decisión de inversión es de quien la toma, no suya. Vídeo con patrocinio declarado de Mintos.

**Activos mencionados:** Bitcoin (67.000 superado, 83.000 pendiente; objetivos 250.000-840.000 a 4 años), Ethereum (1.850 superado, 2.450 pendiente), Solana (doble suelo, objetivo 150), Ripple (rango 12-18 sin romper), Cardano (débil, soporte perdido), Nasdaq 100 y oro (relativos con Bitcoin en progreso, sin romper).

**Tono:** cautelosamente optimista — reconoce señales tempranas de fin de ciclo bajista, pero remarca explícitamente que faltan confirmaciones antes de darlo por hecho.

**Nota de bug del pipeline:** el script `download_transcripts.py` guarda cada transcript como `{fecha}-{canal}.txt` sin distinguir por `video_id`. Cuando revisa los últimos 3 vídeos de un canal, en cuanto encuentra que `{fecha}-{canal}.txt` ya existe lo descarta como duplicado sin comprobar si es un vídeo distinto — el sufijo `-{video_id}` que el propio código contempla para este caso nunca llega a activarse porque la comprobación de "ya existe" ocurre antes. Por eso, si un canal publica dos vídeos el mismo día, solo se guarda el primero que procesa el script.
