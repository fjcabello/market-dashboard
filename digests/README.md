# digests/

Digest diario por Telegram de los resúmenes nuevos.

- `YYYY-MM-DD.md`: lo escribe `/daily-resumenes` cuando genera resúmenes nuevos. Lleva una sección `## <nombre del resumen>` por vídeo, con 1-2 frases.
- `YYYY-MM-DD.partial`: cuántos mensajes de un digest largo se enviaron ya, si el envío falló a mitad. La siguiente ejecución sigue desde ahí y lo borra al terminar.
- `YYYY-MM-DD.sent`: marcador que crea `tools/send_digest.py` cuando Telegram acepta el envío. Mientras no exista, el digest se intenta enviar en cada ejecución de `daily_resumenes.yml`, salvo entre las 23:00 y las 07:00 de Madrid.

Para previsualizar sin enviar: `python3 tools/send_digest.py --dry-run`.
