#!/usr/bin/env python3
"""band_discography_batch.py — Discografía Spotify incremental (amable con la cuota dev mode).

Procesa hasta N bandas sin 'spotify_discografia' en data/bands.json (por defecto 3),
usando el ID verificado (KNOWN_IDS / metricas.spotify_artist_id) y sleep entre bandas.
Pensado para cron diario local: completa el catálogo poco a poco sin morir por 429.

Uso:
  python3 scripts/band_discography_batch.py [N]
  (requiere SPOTIFY_CLIENT_ID/SECRET en el entorno; usa run_metrics.sh como wrapper)
"""
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BANDS = REPO / 'data' / 'bands.json'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SLEEP = 45


def main():
    bands = json.loads(BANDS.read_text(encoding='utf-8'))
    pendientes = [b for b in bands if b != 'meta'
                  and 'spotify_discografia' not in bands[b].get('metricas', {})]
    if not pendientes:
        print('✅ Todas las bandas ya tienen discografía Spotify. Nada que hacer.')
        return 0
    todo = pendientes[:N]
    print(f'Pendientes: {len(pendientes)} → proceso {len(todo)}: {", ".join(todo)}')
    env = dict(os.environ)
    for k in ('SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET'):
        if k not in env:
            print(f'ERROR: falta {k} en el entorno')
            return 1
    for i, band in enumerate(todo):
        print(f'>>> [{i+1}/{len(todo)}] {band}')
        r = subprocess.run([sys.executable, 'scripts/band_metrics_spotify.py',
                            '--band', band, '--discography'],
                           cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
        print(r.stdout[-800:] or r.stderr[-300:])
        if i < len(todo) - 1:
            time.sleep(SLEEP)
    rest = [b for b in pendientes if b not in todo]
    print(f'Quedan {len(rest)}: {", ".join(rest)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
