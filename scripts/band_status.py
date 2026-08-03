#!/usr/bin/env python3
"""band_status.py — Estado de actividad de las bandas de la escena.

Criterios (regla del usuario, agosto 2026):
- ACTIVA      : publicó en el mes en curso o el anterior.
- SOSPECHOSA  : lleva 1 mes completo sin publicar.
- INACTIVA    : lleva 2+ meses sin publicar (o anunció retirada/parón).
  → Las INACTIVAS se marcan para dejar de seguirlas; se quitan de la
    plantilla titular (Lo Gordo) y su ficha muestra badge. NUNCA se borran
    sus datos: la DB conserva el histórico.

Salida: media/band_status.json  { band: {status, last_post, months_inactive, note} }
Uso: python3 scripts/band_status.py [--month YYYY-MM]
"""
import json, re, sqlite3, sys
from datetime import datetime, timedelta
from pathlib import Path

DB = Path.home() / '.hermes' / 'folk_metal_posts.db'
OUT = Path('/home/roa/github/folk-metal-magazine') / 'media' / 'band_status.json'

RETIRO_ANUNCIO = re.compile(
    r'anunciamos nuestra retirada|anunciamos el fin|nos retiramos|dejamos los escenarios|'
    r'adiós definitivo|ponemos punto final|última gira|nos despedimos definitivamente', re.I)

def main():
    month = None
    if '--month' in sys.argv:
        month = sys.argv[sys.argv.index('--month') + 1]
    ref = datetime.strptime(month, '%Y-%m') if month else datetime.now().replace(day=1)

    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT band_name, MAX(post_date) as last FROM posts GROUP BY band_name").fetchall()
    # Conciertos futuros: actividad real aunque no publique en redes
    futuros = {}
    for b, n in conn.execute(
            "SELECT band_name, COUNT(*) FROM concerts WHERE date >= ? GROUP BY band_name",
            (ref.strftime('%Y-%m-%d'),)):
        futuros[b] = n
    conn.close()

    status = {}
    for band, last in rows:
        if not last:
            continue
        last_dt = datetime.strptime(last[:10], '%Y-%m-%d')
        # meses de inactividad relativos al primer día del mes de referencia
        months = (ref.year - last_dt.year) * 12 + (ref.month - last_dt.month)
        # anuncio de retirada en captions recientes (últimos 3 meses)
        conn = sqlite3.connect(DB)
        recent = conn.execute(
            "SELECT caption FROM posts WHERE band_name=? AND post_date >= ?",
            (band, (ref - timedelta(days=90)).strftime('%Y-%m-%d'))).fetchall()
        conn.close()
        anuncio = any(RETIRO_ANUNCIO.search(c[0] or '') for c in recent)

        if anuncio:
            st = 'INACTIVA'
            note = 'anuncio de retirada/parón'
        elif futuros.get(band, 0) > 0:
            st = 'ACTIVA'
            note = f'activa vía conciertos ({futuros[band]} futuros)'
        elif months >= 2:
            st = 'INACTIVA'
            note = f'{months} meses sin publicar'
        elif months >= 1:
            st = 'SOSPECHOSA'
            note = f'{months} mes(es) sin publicar'
        else:
            st = 'ACTIVA'
            note = ''
        status[band] = {'status': st, 'last_post': last[:10], 'months_inactive': months, 'note': note}

    OUT.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding='utf-8')

    n = {'ACTIVA': 0, 'SOSPECHOSA': 0, 'INACTIVA': 0}
    for v in status.values():
        n[v['status']] += 1
    print(f'band_status: ACTIVA={n["ACTIVA"]} SOSPECHOSA={n["SOSPECHOSA"]} INACTIVA={n["INACTIVA"]} → {OUT}')
    for b, v in sorted(status.items()):
        if v['status'] != 'ACTIVA':
            print(f'  {v["status"]:11s} {b} (último {v["last_post"]}) {v["note"]}')

if __name__ == '__main__':
    main()
