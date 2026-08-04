#!/usr/bin/env python3
"""band_ranking_spotify.py — Ranking de bandas de folk metal en español por oyentes mensuales.

Contrasta la lista de la revista (data/bands.json) con el resto de la escena:
1. Busca en Spotify (API, search) bandas de folk metal en español: las de la
   plantilla + queries de descubrimiento ('folk metal español', 'folk metal
   latinoamericano', nombres de escena conocidos).
2. Para cada artista, scrapea la página pública (open.spotify.com/intl-es/artist/ID)
   y extrae el og:description → "Artist · 1.8K monthly listeners".
3. Clasifica: españolas (nuestras + descubiertas) vs latinoamericanas (apartado).

Nota dev-mode: la API no da followers/popularity; el scrape del og:description
sí da los oyentes mensuales reales que muestra Spotify al público.

Uso:
  python3 scripts/band_ranking_spotify.py                # todo
  python3 scripts/band_ranking_spotify.py --solo-plantilla  # solo las 29 de la revista
Salida: data/ranking_spotify.json
"""
import json, os, re, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parent.parent
BANDS_PATH = REPO / 'data' / 'bands.json'
OUT = REPO / 'data' / 'ranking_spotify.json'
API = 'https://api.spotify.com/v1'
# UA simple: con el UA completo de Chrome, Spotify sirve consent wall y no hay
# og:description; con 'Mozilla/5.0' a secas devuelve la página pública real.
UA = 'Mozilla/5.0'

# Queries de descubrimiento: nombres de escena y bandas conocidas del folk
# metal en español (fuera de nuestra plantilla de 29).
DISCOVERY = [
    'folk metal español', 'folk metal España', 'folk metal latinoamericano',
    'Mägo de Oz', 'Saurom', 'Salduie', 'Celtian', 'Lèpoka', 'Lándevir',
    'Hadadanza', 'Celtibeerian', 'Nidhögg', 'Tierra Santa', 'Saurom Lamderth',
    'Mago de Oz', 'folk metal mexicano', 'Mägo', 'Lepoka', 'Celtian',
    'Drakum', 'Hibérnia', 'Ars Amandi', 'Lurte', 'Stravaganzza',
    'Argentum', 'Ancestral', 'Valkiria', 'Runa Llena', 'Wyrdamur', 'Mileth',
    'Taranus', 'Nörth', 'Kharma', 'Saurom', 'Ganso & Crow', 'Salduie',
    'Folkestone', 'Santuario', 'Jar', 'Lándevir', 'Triskel', 'Kinnia',
]


def get_token():
    import base64
    env = Path.home().joinpath('.hermes/.env').read_text()
    def _g(k):
        for line in env.splitlines():
            if line.startswith(k + '='):
                return line.split('=', 1)[1].strip()
        return ''
    cid, csec = _g('SPOTIFY_CLIENT_ID'), _g('SPOTIFY_CLIENT_SECRET')
    refresh = _g('SPOTIFY_REFRESH_TOKEN')
    if refresh:
        body = urlencode({'grant_type': 'refresh_token', 'refresh_token': refresh,
                          'client_id': cid}).encode()
        req = Request('https://accounts.spotify.com/api/token', data=body, headers={
            'Authorization': 'Basic ' + base64.b64encode(f'{cid}:{csec}'.encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            with urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())['access_token'], 'user'
        except Exception:
            pass
    auth = base64.b64encode(f'{cid}:{csec}'.encode()).decode()
    body = urlencode({'grant_type': 'client_credentials'}).encode()
    req = Request('https://accounts.spotify.com/api/token', data=body, headers={
        'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())['access_token'], 'client'


def api_search(token, query, limit=5):
    q = urlencode({'q': query, 'type': 'artist', 'limit': limit})
    req = Request(API + f'/search?{q}', headers={'Authorization': f'Bearer {token}'})
    try:
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get('artists', {}).get('items', [])
    except Exception:
        return []


def listeners_from_page(artist_id):
    """og:description de la página pública → oyentes mensuales."""
    try:
        r = subprocess.run(
            ['curl', '-sL', '--max-time', '15', '-A', UA,
             f'https://open.spotify.com/intl-es/artist/{artist_id}'],
            capture_output=True, text=True, timeout=25)
        # Buscar en cualquier orden de atributos: property/content o content/property
        m = re.search(r'og:description"[^>]*content="(Artist|Artista) · ([\d.,]+[KM]?)\s+(monthly listeners|oyentes mensuales)', r.stdout)
        if m:
            return m.group(2)
        m2 = re.search(r'content="(Artist|Artista) · ([\d.,]+[KM]?)\s+(monthly listeners|oyentes mensuales)"[^>]*og:description', r.stdout)
        if m2:
            return m2.group(2)
    except Exception:
        pass
    return None


def parse(v):
    v = (v or '').replace(',', '').upper()
    try:
        if v.endswith('M'):
            return float(v[:-1]) * 1_000_000
        if v.endswith('K'):
            return float(v[:-1]) * 1_000
        return float(v)
    except ValueError:
        return -1


def norm_name(s):
    return ''.join(c for c in s.casefold() if c.isalnum())


def es_banda_relevante(name, query):
    """Filtra miembros/variantes que no son la banda buscada (ej. 'Sergio Reino
    de Hades', 'Nuria Ekyrian', 'Xeria.0', 'The Triskells')."""
    n = norm_name(name)
    q = norm_name(query)
    if not q:
        return True
    # Variantes del mismo nombre (Lépoka vs Lèpoka, XERIA vs Xeria) OK
    if q in n or n in q:
        return True
    # Patrones claros de no-banda: nombre + apellido/rol delante
    if re.search(r'\b(gus|nuria|jevo|josé|jose|sergio|angel|bianka|nem|the)\b', name.casefold()):
        return False
    return True


def main():
    token, mode = get_token()
    print(f'token: {mode}')
    bands = json.loads(BANDS_PATH.read_text(encoding='utf-8'))
    plantilla = [b for b in bands if b != 'meta']

    found = {}   # artist_id -> {name, listeners}
    if '--solo-plantilla' not in sys.argv:
        for q in DISCOVERY:
            items = api_search(token, q, limit=5)
            for a in items:
                aid = a['id']
                if aid not in found:
                    found[aid] = {'name': a['name'], 'id': aid, 'query': q}
            time.sleep(0.4)

    # Añadir las de la plantilla (búsqueda por nombre exacto)
    for band in plantilla:
        items = api_search(token, f'artist:"{band}"', limit=3)
        for a in items:
            aid = a['id']
            if aid not in found and es_banda_relevante(a['name'], band):
                found[aid] = {'name': a['name'], 'id': aid, 'query': band}
        time.sleep(0.4)

    # Scrape oyentes de cada artista (secuencial, cuota amable)
    results = []
    for aid, info in found.items():
        lst = listeners_from_page(aid)
        info['listeners'] = lst
        results.append(info)
        print(f"  {lst or '—':>10}  {info['name']}")
        time.sleep(0.8)

    # Clasificación geográfica aproximada: marcamos las de la plantilla como
    # 'nuestra'; el resto se etiqueta por país de forma manual/heurística.
    plantilla_lower = {b.casefold() for b in plantilla}
    for r in results:
        r['en_plantilla'] = r['name'].casefold() in plantilla_lower or \
            any(p in r['name'].casefold() for p in plantilla_lower if len(p) > 4)
        r['valor'] = parse(r.get('listeners'))

    results.sort(key=lambda x: x['valor'], reverse=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f'\n=== RANKING por oyentes mensuales → {OUT} ===')
    print(f'Total artistas encontrados: {len(results)}')
    print('\nTop 15:')
    for r in results[:15]:
        marca = '★' if r['en_plantilla'] else ' '
        print(f"  {marca} {r['listeners'] or '—':>10}  {r['name']}")
    print('\nEn nuestra plantilla de 29:')
    for r in results:
        if r['en_plantilla']:
            print(f"  {r['listeners'] or '—':>10}  {r['name']}")


if __name__ == '__main__':
    main()
