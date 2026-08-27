# Cotización de oro (fuera de Libra)

Este mini-repo mantiene un histórico diario del precio del oro en `historico.json`,
para que el widget HTML lo lea desde cualquier navegador (dentro o fuera de Libra),
sin depender de la red interna ni de CORS.

Cómo funciona: un GitHub Action (`.github/workflows/actualizar-oro.yml`) se
ejecuta una vez al día, corre `scripts/actualizar_oro.py`, y ese script consulta
el precio del oro (servidor a servidor, sin problema de CORS porque no hay
navegador de por medio) y actualiza `historico.json` con un commit. GitHub sirve
ese fichero en `https://raw.githubusercontent.com/...` con la cabecera
`Access-Control-Allow-Origin: *`, así que cualquier página puede leerlo con
`fetch()` sin bloqueos.

## Puesta en marcha (una vez)

1. Crea un repositorio **público** en GitHub (tiene que ser público para que
   `raw.githubusercontent.com` sirva el fichero sin necesitar token de acceso;
   `historico.json` solo va a tener fechas y precios, nada personal).
2. Sube estos archivos manteniendo la estructura de carpetas:
   - `.github/workflows/actualizar-oro.yml`
   - `scripts/actualizar_oro.py`
   - `historico.json`
   - `README.md` (opcional)
3. Ve a la pestaña **Actions** del repo. Si GitHub pide habilitarlas, acéptalo.
4. Lanza el workflow a mano una vez para comprobar que funciona: Actions →
   "Actualizar cotización del oro" → botón **Run workflow**. Debería terminar
   en verde y dejar un commit con el precio de hoy en `historico.json`.
5. Copia esta URL, sustituyendo `TU_USUARIO` y `TU_REPO`:

   ```
   https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/historico.json
   ```

6. Pásame esa URL (o sustitúyela tú mismo) en la constante `HISTORICO_URL` de
   `widget_oro.html`.

A partir de ahí, el Action se ejecuta solo cada día a las 07:00 UTC. Si algún
día ambas fuentes de precio fallan, el workflow termina en rojo (verás el aviso
en GitHub / por email) en vez de dejar el histórico desactualizado en silencio.

## Añadir más días de golpe / corregir un dato

Edita `historico.json` a mano (o añade entradas) y haz commit; el formato es:

```json
[
  { "fecha": "2026-08-27", "precioGramoEur": 127.33, "precioOnzaEur": 3960.8, "origen": "goldprice.dev", "computedAt": "2026-08-27T07:00:00Z" }
]
```

## Si las dos fuentes gratuitas dejan de responder

`scripts/actualizar_oro.py` prueba `goldprice.dev` y, si falla,
`goldprice.org`. Si con el tiempo ambas fallan a menudo, añade una función
`fuente_...()` nueva siguiendo el mismo patrón (por ejemplo una API con clave
gratuita, guardando la clave como "repository secret" en GitHub → Settings →
Secrets and variables → Actions, y leyéndola en el script con
`os.environ["NOMBRE_SECRETO"]`).
