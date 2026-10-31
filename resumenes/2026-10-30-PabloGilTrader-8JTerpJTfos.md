# 2026-10-30 — PabloGilTrader

**Tesis principal:** Vídeo monográfico sobre el **hackeo de Binance** comunicado el 30 de octubre, con un impacto estimado de unos **6.300 M$** y las retiradas suspendidas temporalmente. Pablo Gil separa hechos de hipótesis: hay unos **3.000 M** congelados y unos **3.300 M** de destino incierto, una atribución todavía no confirmada a Corea del Norte y un compromiso de Binance de reembolsar con recursos propios. Insiste en que la lección no va del precio, sino del **riesgo de contraparte**: distinguir seguridad, liquidez y solvencia, y valorar la autocustodia en wallet fría, que "desplaza los riesgos, pero no los elimina". No da niveles de Bitcoin.

**Puntos clave:**

- **Magnitud:**
  - Impacto estimado de **~6.300 M$** según lo comunicado inicialmente. El ataque a **Bybit** de febrero de 2025, uno de los mayores conocidos hasta ahora, afectó a unos **1.500 M**, así que este sería "más de cuatro veces superior".
  - "Una cifra comprometida no equivale necesariamente a una pérdida definitiva".

- **Lo congelado y lo pendiente:**
  - Binance dice haber trabajado con otros actores del sector para **congelar ~3.000 M$**. Quedan **~3.300 M** cuya situación final no está aclarada.
  - "Congelar no significa recuperar": hay procesos técnicos, jurídicos y de coordinación que pueden tardar.
  - Algunas *stablecoins* emitidas por empresas permiten bloquear tokens en direcciones concretas. **Bitcoin no tiene emisor** que pueda congelar monedas unilateralmente, lo que condiciona la capacidad de los atacantes para mover o convertir los fondos.

- **Cómo pudo ocurrir (información preliminar):**
  - Los atacantes habrían comprometido "el portátil de un ingeniero de Box" y desde ahí habrían interferido en la **infraestructura de firma y autorización de transacciones** de Binance. **A señalar:** "Box" puede ser un error de transcripción; no queda claro si se refiere a un proveedor externo o a otra cosa.
  - Binance dice que por ahora **no hay pruebas de filtración de las claves privadas** de sus monederos. Lección: "no basta con proteger las claves, también hay que proteger los sistemas que procesan y autorizan las órdenes" (la analogía de la caja fuerte y el sistema que decide cuándo se abre).

- **Atribución a Corea del Norte:**
  - Algunas firmas de análisis *blockchain* apuntan a actores vinculados a Corea del Norte. "Una atribución de una empresa de inteligencia no equivale a una sentencia judicial".
  - Precedente: el FBI atribuyó a actores norcoreanos el ataque a Bybit de 2025. Hay una dimensión geopolítica: con grupos vinculados a estados, rastrear en la *blockchain* no implica poder detener a los responsables ni recuperar los fondos.

- **Clientes y reembolso:**
  - Binance se compromete a reembolsar las pérdidas **con recursos propios**. Según CoinDesk, ha dispuesto **~6.340 M$**, lo que no significa que vaya a perder toda esa cantidad, porque parte de lo comprometido está congelado.
  - Existe el fondo **SAFU** de protección de usuarios, pero "no debemos dar por hecho" que vaya a financiar estas compensaciones. Lo confirmado es el uso de recursos propios.

- **Seguridad, liquidez y solvencia:**
  - Seguridad es impedir accesos no autorizados. Liquidez, atender las retiradas. Solvencia, tener activos suficientes para cubrir las obligaciones.
  - "Un incidente de seguridad no demuestra automáticamente insolvencia, pero puede desencadenar una crisis de confianza que termina afectando a la liquidez". De ahí el nerviosismo por la suspensión de retiradas. No es lo mismo que un activo baje porque el mercado vende que no poder moverlo porque el intermediario ha paralizado las operaciones.

- **Por qué cayó Bitcoin:**
  - No por una vulnerabilidad del protocolo, sino por la incertidumbre: hay reducción de exposición, búsqueda de liquidez y el apalancamiento amplifica los movimientos con liquidaciones en cascada.
  - "Sería un error atribuir toda la debilidad reciente" al incidente. También pesan las expectativas de tipos, la liquidez global, el apetito por el riesgo y los flujos. "Un *shock* de confianza puede ser el detonante de una caída sin ser necesariamente su única causa". No da precios ni porcentajes de la caída.

- **Wallet fría frente a exchange:**
  - La diferencia clave es **quién controla las claves privadas**. En una wallet fría de autocustodia, un hackeo de la infraestructura de firma de Binance no da acceso a tus claves y no necesitas que Binance autorice una retirada.
  - **No es seguridad absoluta:** si pierdes la frase de recuperación, pierdes los fondos. Si alguien la obtiene, puede robarlos, y la wallet no te protege de firmar tú mismo una operación fraudulenta o de enviar a una dirección equivocada.
  - Su propuesta: una cantidad limitada en plataforma para quien opera a menudo, estudiar la autocustodia para el largo plazo "siempre que se comprendan bien sus exigencias técnicas" o una custodia profesional con controles adecuados. "Si no controlas tus claves, no controlas directamente tus monedas", aunque reconoce que es una simplificación.

- **Qué vigilar:** cuánto se recupera realmente, qué revela el informe técnico, si se confirma la atribución y cómo responde Binance a sus clientes. "No tenemos todavía todas las respuestas y sería irresponsable fingir que sí".

- **Promoción propia (conflicto de interés):** anuncia dos veces un directo gratuito el **9 de noviembre a las 19:07** (hora de Madrid) sobre decisiones de inversión en entornos de incertidumbre, con análisis macro, geopolítico, de bolsa, Bitcoin, oro y *altcoins*. El enlace está en la descripción. Avisa de suplantaciones: no contacta por Telegram ni WhatsApp. Aclara que no da recomendaciones personalizadas.

**Activos mencionados:** Binance (hackeo de ~6.300 M$; ~3.000 M congelados; ~3.300 M pendientes; ~6.340 M dispuestos para reembolsos según CoinDesk), Bybit (hackeo de ~1.500 M en febrero de 2025), Bitcoin (caída sin niveles), *stablecoins* (congelables), *altcoins*.

**Tono:** neutro / educativo, centrado en el riesgo de contraparte. Prudente: no extrapola el incidente a una tesis bajista sobre Bitcoin.

**Contraste con otros canales:** Jaime Merino comentó el mismo hackeo en directo la noche del 29 ([[2026-10-30-TradingLatino]]): suspensión de retiros de 24 horas, Bitcoin en ~77.400-77.600 y una insinuación de "autohackeo" que Pablo Gil no recoge. Los dos coinciden en no atribuir toda la caída de Bitcoin al incidente. Merino no daba la cifra de 6.300 M.
