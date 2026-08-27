#!/usr/bin/env python3
"""
Consulta la cotización spot del oro (XAU/EUR) y actualiza historico.json
con el precio de hoy. Pensado para ejecutarse desde un GitHub Action diario
(ver .github/workflows/actualizar-oro.yml).

Prueba varias fuentes en orden hasta que una responda; si todas fallan,
termina con error de salida distinto de cero para que el Action falle de
forma visible (y GitHub avise por email) en vez de dejar el histórico
desactualizado en silencio.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone

TROY_OZ_TO_GRAM = 31.1034768
HISTORICO_PATH = "historico.json"
DIAS_A_CONSERVAR = 365  # recorta el fichero para que no crezca indefinidamente

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


def cargar_historico():
    try:
        with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def guardar_historico(entradas):
    entradas = sorted(entradas, key=lambda e: e["fecha"])[-DIAS_A_CONSERVAR:]
    with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
        json.dump(entradas, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    precio_onza, origen = obtener_precio_onza_eur()
    precio_gramo = precio_onza / TROY_OZ_TO_GRAM
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    historico = cargar_historico()
    historico = [e for e in historico if e.get("fecha") != hoy]
    historico.append(
        {
            "fecha": hoy,
            "precioGramoEur": round(precio_gramo, 4),
            "precioOnzaEur": round(precio_onza, 4),
            "origen": origen,
            "computedAt": ahora,
        }
    )
    guardar_historico(historico)
    print(f"OK: {hoy} -> {precio_gramo:.4f} EUR/g (fuente: {origen})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR actualizando cotizacion: {exc}", file=sys.stderr)
        sys.exit(1)
