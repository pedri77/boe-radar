#!/usr/bin/env python3
"""Descarga los sumarios XML del BOE via la API de datos abiertos oficial.

Punto de entrada REAL (documentado en APIsumarioBOE.pdf, 28/06/2024):
  GET https://boe.es/datosabiertos/api/boe/sumario/{AAAAMMDD}
  Cabecera Accept: application/xml
El endpoint antiguo /diario_boe/xml.php?id=BOE-S-<fecha> YA NO funciona para
sumarios (302 -> errorParametros.php); si funciona para disposiciones sueltas
(BOE-A-*), pero el sumario por día es lo que necesitamos.

Respuestas medidas:
  200 -> sumario del día (XML <response><data><sumario>...)
  404 -> no hay BOE ese día (domingos sin BOE y festivos sin publicación)

Cada día se cachea en raw/sumarios/AAAAMMDD.xml: reejecutar no re-descarga.
Corte elegido: año natural 2025 completo (2025-01-01 a 2025-12-31).
"""
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "raw" / "sumarios"
URL = "https://boe.es/datosabiertos/api/boe/sumario/{}"
UA = {"Accept": "application/xml", "User-Agent": "boe-radar/1.0 (episodio cci-10)"}
DELAY = 0.25  # sin límite de tasa documentado; pausa de cortesía


def fetch(day: date, retries: int = 3) -> tuple[int, int]:
    dst = RAW / f"{day:%Y%m%d}.xml"
    if dst.exists():
        return 0, dst.stat().st_size
    req = urllib.request.Request(URL.format(day.strftime("%Y%m%d")), headers=UA)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            dst.write_bytes(body)
            return 200, len(body)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                (RAW / f"{day:%Y%m%d}.404").write_text(
                    f"HTTP {e.code} - sin BOE este día\n")
                return 404, 0
            if attempt == retries - 1:
                (RAW / f"{day:%Y%m%d}.err").write_text(f"HTTP {e.code}\n")
                return e.code, 0
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # red
            if attempt == retries - 1:
                (RAW / f"{day:%Y%m%d}.err").write_text(f"{e}\n")
                return -1, 0
            time.sleep(2 * (attempt + 1))
    return -1, 0


def main() -> None:
    start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2025, 1, 1)
    end = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2025, 12, 31)
    RAW.mkdir(parents=True, exist_ok=True)
    counts = {200: 0, 404: 0, "cache": 0, "error": 0}
    day = start
    while day <= end:
        code, size = fetch(day)
        if code == 0:
            counts["cache"] += 1
        elif code in (200, 404):
            counts[code] += 1
        else:
            counts["error"] += 1
        if code in (200, -1) or code == 0:
            pass
        if code != 0:
            time.sleep(DELAY)
        day += timedelta(days=1)
    print(f"OK={counts[200]} cache={counts['cache']} sin-BOE(404)={counts[404]} "
          f"errores={counts['error']}  ({start}..{end})")


if __name__ == "__main__":
    main()
