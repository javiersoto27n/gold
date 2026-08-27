#!/usr/bin/env python3
"""
Consulta la cotización spot del oro (XAU/EUR) y añade un punto intradía a
historico.json. Pensado para ejecutarse desde un GitHub Action cada 2 horas,
de lunes a viernes (ver .github/workflows/actualizar-oro.yml).

Cada ejecución se redondea a su franja de 2 horas (00,02,04...22 UTC) y
sustituye la entrada de esa franja si ya existía (para que relanzar el job a
mano no duplique puntos); franjas distintas se van acumulando, así que un
mismo día puede tener varios puntos.

Prueba varias fuentes en orden hasta que una responda; si todas fallan,
termina con error de salida distinto de cero para que el Action falle de
forma visible (y GitHub avise por email) en vez de dejar el histórico
desactualizado en silencio.
"""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

TROY_OZ_TO_GRAM = 31.1034768
HISTORICO_PATH = "historico.json"
DIAS_A_CONSERVAR = 180  # recorta por ventana de fechas (no por nº de puntos)
FRANJA_HORAS = 2  # tamaño de la franja intradía en horas (debe cuadrar con el cron)

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fuente_goldprice_dev():
    """https://goldprice.dev - endpoint anonimo, sin API key, JSON."""
    data = _get_json(
        "https://api.goldprice.dev/v1/prices?symbol=XAU-EUR-SPOT",
        headers={"Accept": "application/json", "User-Agent": BROWSER_USER_AGENT},
    )
    precio_onza = float(data["symbols"][0]["price"])
    return precio_onza, "goldprice.dev"


def fuente_goldprice_org():
    """Endpoint publico que usa el ticker embebible de goldprice.org."""
    data = _get_json(
        "https://data-asg.goldprice.org/dbXRates/EUR",
        headers={
            "Accept": "application/json",
            "User-Agent": BROWSER_USER_AGENT,
            "Referer": "https://goldprice.org/",
        },
    )
    precio_onza = float(data["items"][0]["xauPrice"])
    return precio_onza, "goldprice.org"


# Añade aquí más fuentes si estas dos empiezan a fallar con frecuencia
# (por ejemplo una API con clave gratuita, guardando la clave como
# "repository secret" en GitHub y leyéndola con os.environ).
FUENTES = [fuente_goldprice_dev, fuente_goldprice_org]


def obtener_precio_onza_eur():
    errores = []
    for fuente in FUENTES:
        try:
            precio, nombre = fuente()
            if precio and precio > 0:
                return precio, nombre
        except Exception as exc:  # queremos capturar cualquier fallo de red/parseo
            errores.append(f"{fuente.__name__}: {exc}")
    raise RuntimeError("Ninguna fuente de cotizacion respondio. Detalle: " + " | ".join(errores))


def migra_entrada(entrada):
    """Rellena 'hora'/'timestamp' en entradas del formato antiguo (un solo
    punto por día, sin franja horaria), usando fecha + computedAt si existe."""
    if "timestamp" in entrada and "hora" in entrada:
        return entrada
    fecha = entrada.get("fecha", "1970-01-01")
    hora = "00:00"
    computed_at = entrada.get("computedAt", "")
    if computed_at and "T" in computed_at:
        hora = computed_at.split("T", 1)[1][:5]
    entrada = dict(entrada)
    entrada.setdefault("hora", hora)
    entrada.setdefault("timestamp", f"{fecha}T{hora}:00Z")
    return entrada


def cargar_historico():
    try:
        with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [migra_entrada(e) for e in datos]


def guardar_historico(entradas):
    limite = (datetime.now(timezone.utc) - timedelta(days=DIAS_A_CONSERVAR)).strftime("%Y-%m-%d")
    entradas = [e for e in entradas if e.get("fecha", "") >= limite]
    entradas = sorted(entradas, key=lambda e: e["timestamp"])
    with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
        json.dump(entradas, f, ensure_ascii=False, indent=2)
        f.write("\n")


def franja_actual():
    """Redondea 'ahora' hacia abajo a su franja de FRANJA_HORAS horas (UTC)."""
    ahora = datetime.now(timezone.utc)
    hora_franja = (ahora.hour // FRANJA_HORAS) * FRANJA_HORAS
    return ahora.replace(hour=hora_franja, minute=0, second=0, microsecond=0)


def main():
    precio_onza, origen = obtener_precio_onza_eur()
    precio_gramo = precio_onza / TROY_OZ_TO_GRAM

    slot = franja_actual()
    fecha = slot.strftime("%Y-%m-%d")
    hora = slot.strftime("%H:%M")
    timestamp = slot.strftime("%Y-%m-%dT%H:%M:00Z")
    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    historico = cargar_historico()
    historico = [e for e in historico if e.get("timestamp") != timestamp]
    historico.append(
        {
            "fecha": fecha,
            "hora": hora,
            "timestamp": timestamp,
            "precioGramoEur": round(precio_gramo, 4),
            "precioOnzaEur": round(precio_onza, 4),
            "origen": origen,
            "computedAt": computed_at,
        }
    )
    guardar_historico(historico)
    print(f"OK: {timestamp} -> {precio_gramo:.4f} EUR/g (fuente: {origen})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR actualizando cotizacion: {exc}", file=sys.stderr)
        sys.exit(1)
