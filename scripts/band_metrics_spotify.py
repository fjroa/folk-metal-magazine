#!/usr/bin/env python3
"""band_metrics_spotify.py — Métricas reales de Spotify por banda vía API oficial.

Reemplaza el scrape de web_search: con un Client ID/Secret de una app de
Spotify Developer (gratis, developer.spotify.com/dashboard) obtenemos datos
oficiales por artista:
  - followers (seguidores)
  - popularity (0-100)
  - top 10 tracks con popularity y duración
  - artist URI para enlazar

Flujo Client Credentials (no necesita cuenta de usuario; solo la app):
  1. POST https://accounts.spotify.com/api/token  (client_id + client_secret)
  2. GET  /v1/artists/{id} → followers, popularity
  3. GET  /v1/artists/{id}/top-tracks?market=ES → top tracks

Resuelve el ID de artista por nombre vía /v1/search si no se pasa --id.

Escribe en data/bands.json → metricas.spotify_* (por banda), conservando
spotify_oyentes_mes manual si no hay API.

Uso:
  SPOTIFY_CLIENT_ID=xxx SPOTIFY_CLIENT_SECRET=yyy \
    python3 scripts/band_metrics_spotify.py [--band "Reino de Hades"] [--id 2cPuCPULrrKqi5guQ0Que7]
"""
import json, os, re, subprocess, sys, time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parent.parent
BANDS_PATH = REPO / 'data' / 'bands.json'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API = 'https://api.spotify.com/v1'

CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')

# IDs de artista ya conocidos (ahorran búsqueda). Se pueden ampliar.
KNOWN_IDS = {
    'Reino de Hades': '2cPuCPULrrKqi5guQ0Que7',
}


def get_token(user=False):
    import base64
    if user:
        # Authorization Code flow: refresh_token del usuario (acceso completo).
        env = Path.home().joinpath('.hermes/.env').read_text()
        def _g(k):
            for line in env.splitlines():
                if line.startswith(k + '='):
                    return line.split('=', 1)[1].strip()
            return ''
        refresh = _g('SPOTIFY_REFRESH_TOKEN')
        if not refresh:
            raise RuntimeError('sin SPOTIFY_REFRESH_TOKEN — ejecuta scripts/spotify_auth.py --url primero')
        body = urlencode({
            'grant_type': 'refresh_token',
            'refresh_token': refresh,
            'client_id': CLIENT_ID,
        }).encode()
        req = Request(TOKEN_URL, data=body, headers={
            'Authorization': 'Basic ' + base64.b64encode(
                f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded',
        })
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())['access_token']
    auth = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
    body = urlencode({'grant_type': 'client_credentials'}).encode()
    req = Request(TOKEN_URL, data=body, headers={
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())['access_token']


def api_get(token, path, retries=5):
    for attempt in range(retries):
        try:
            req = Request(API + path, headers={'Authorization': f'Bearer {token}'})
            with urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                # Dev mode: cuota muy baja (~25 req/ventana). Esperar generoso.
                time.sleep(30 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            raise


def search_artist(token, name):
    q = urlencode({'q': name, 'type': 'artist', 'limit': 5})
    data = api_get(token, f'/search?{q}')
    items = data.get('artists', {}).get('items', [])
    if not items:
        return None
    # Verificar coincidencia: el nombre del artista debe contener el buscado o
    # viceversa (normalizando). Evita falsos positivos (ej. 'Lèpoka' → 'Bleed
    # From Within'; 'Lándevir' → 'Los gandules').
    norm = lambda s: ''.join(c for c in s.casefold() if c.isalnum())
    target = norm(name)
    for a in items:
        cand = norm(a.get('name', ''))
        if target and (target in cand or cand in target):
            return {'id': a['id'], 'name': a['name'], 'uri': a['uri'],
                    'followers': a.get('followers', {}).get('total', 0),
                    'popularity': a.get('popularity', 0)}
    return None


def fetch_artist(token, artist_id):
    data = api_get(token, f'/artists/{artist_id}')
    return {'id': data['id'], 'name': data['name'], 'uri': data['uri'],
            'followers': data.get('followers', {}).get('total', 0),
            'popularity': data.get('popularity', 0)}


def fetch_top_tracks(token, artist_id, market='ES'):
    data = api_get(token, f'/artists/{artist_id}/top-tracks?market={market}')
    out = []
    for t in data.get('tracks', [])[:10]:
        out.append({
            'titulo': t['name'],
            'popularity': t.get('popularity', 0),
            'duracion_ms': t.get('duration_ms', 0),
            'album': t.get('album', {}).get('name', ''),
            'url': t.get('external_urls', {}).get('spotify', ''),
            'uri': t.get('uri', ''),
        })
    return out


def listeners_from_page(artist_id):
    """og:description de la página pública → oyentes mensuales reales.
    Funciona en dev mode (donde la API no da followers/popularity)."""
    try:
        r = subprocess.run(
            ['curl', '-sL', '--max-time', '15', '-A', 'Mozilla/5.0',
             f'https://open.spotify.com/intl-es/artist/{artist_id}'],
            capture_output=True, text=True, timeout=25)
        m = re.search(r'og:description"[^>]*content="(Artist|Artista) · ([\d.,]+[KM]?)\s+(monthly listeners|oyentes mensuales)', r.stdout)
        if m:
            return m.group(2)
        m2 = re.search(r'content="(Artist|Artista) · ([\d.,]+[KM]?)\s+(monthly listeners|oyentes mensuales)"[^>]*og:description', r.stdout)
        if m2:
            return m2.group(2)
    except Exception:
        pass
    return None


def fetch_discography(token, artist_id):
    """Catálogo verificado (funciona en development mode): álbumes + tracks con URLs.
    Dev mode limita paginación a 10 items por request (limit=50 → 400)."""
    albums = []
    offset = 0
    while True:
        data = api_get(token, f'/artists/{artist_id}/albums?limit=10&offset={offset}&include_groups=album,single')
        items = data.get('items', [])
        if not items:
            break
        for a in items:
            albums.append({
                'titulo': a['name'],
                'tipo': a.get('album_type', ''),
                'fecha': a.get('release_date', ''),
                'url': a.get('external_urls', {}).get('spotify', ''),
                'uri': a.get('uri', ''),
                'total_tracks': a.get('total_tracks', 0),
            })
        offset += len(items)
        if offset >= data.get('total', 0) or len(items) < 10:
            break
    # Dedup por nombre+fecha
    seen, uniq = set(), []
    for a in albums:
        key = (a['titulo'].lower(), a['fecha'])
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    # Tracks del primer álbum full-length
    tracks = []
    full = [a for a in uniq if a['tipo'] == 'album' and a['fecha']]
    if full:
        fid = full[0]['uri'].split(':')[-1]
        try:
            data = api_get(token, f'/albums/{fid}/tracks?limit=10')
            for t in data.get('items', []):
                tracks.append({
                    'titulo': t['name'],
                    'numero': t.get('track_number', 0),
                    'duracion_ms': t.get('duration_ms', 0),
                    'url': t.get('external_urls', {}).get('spotify', ''),
                    'uri': t.get('uri', ''),
                })
        except Exception:
            pass
    return uniq, tracks


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print('ERROR: exporta SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET')
        print('Crea una app gratis en https://developer.spotify.com/dashboard')
        sys.exit(1)
    only = None
    forced_id = None
    use_user = '--user' in sys.argv
    only_disc = '--discography' in sys.argv
    args = [a for a in sys.argv[1:] if a not in ('--user', '--discography')]
    if '--band' in args:
        only = args[args.index('--band') + 1]
    if '--id' in args:
        forced_id = args[args.index('--id') + 1]

    bands = json.loads(BANDS_PATH.read_text(encoding='utf-8'))
    token = get_token(user=use_user)
    print(f'✅ token OK ({"user account" if use_user else "client_credentials"})')

    targets = [only] if only else list(bands.keys())
    for band in targets:
        if band not in bands:
            print(f'  ⚠️ {band} no está en bands.json')
            continue
        try:
            artist_id = forced_id or KNOWN_IDS.get(band)
            if artist_id:
                info = fetch_artist(token, artist_id)
            else:
                info = search_artist(token, band)
                if not info:
                    print(f'  ⚠️ {band}: no encontrado en Spotify')
                    continue
            metricas = bands[band].setdefault('metricas', {})
            metricas['spotify_artist_id'] = info['id']
            metricas['spotify_uri'] = info['uri']
            if info.get('followers'):
                metricas['spotify_followers'] = info['followers']
            if info.get('popularity') is not None:
                metricas['spotify_popularity'] = info['popularity']
            # Oyentes mensuales reales vía og:description (dev mode no los da
            # por API, pero la página pública sí los expone).
            lst = listeners_from_page(info['id'])
            if lst:
                metricas['spotify_oyentes_mes'] = lst
                metricas['spotify_oyentes_nota'] = f'~{lst} oyentes/mes (scrape público, {time.strftime("%Y-%m-%d")})'
            if only_disc:
                albums, tracks = fetch_discography(token, info['id'])
                metricas['spotify_discografia'] = albums
                metricas['spotify_tracks_album_principal'] = tracks
                metricas['spotify_fecha'] = time.strftime('%Y-%m-%d')
                bands[band]['metricas'] = metricas
                n_alb = len(albums)
                n_trk = len(tracks)
                print(f'  ✅ {info["name"]}: {n_alb} álbumes, {n_trk} tracks (catálogo)')
                for a in albums[:5]:
                    print(f'     - {a["fecha"][:4] or "?"} {a["titulo"]} ({a["tipo"]})')
                # Dev mode: cuota baja → pausa generosa entre bandas
                time.sleep(1.5)
                continue
            tracks = fetch_top_tracks(token, info['id'])
            metricas['spotify_top_tracks'] = tracks
            metricas['spotify_fecha'] = time.strftime('%Y-%m-%d')
            bands[band]['metricas'] = metricas
            top3 = '; '.join(t['titulo'] for t in tracks[:3])
            print(f'  ✅ {info["name"]}: {info["followers"]} followers, pop={info["popularity"]}')
            print(f'     top3: {top3}')
            time.sleep(0.3)
        except HTTPError as e:
            # top-tracks 403 en dev mode → fallback: tracks del álbum principal
            # (catálogo) + oyentes del scrape, sin romper.
            if e.code in (403, 429):
                print(f'  ⚠️ {band}: top-tracks {e.code} → catálogo como top (dev mode)')
                try:
                    albums, tracks = fetch_discography(token, info['id'])
                    metricas = bands[band].setdefault('metricas', {})
                    metricas['spotify_discografia'] = albums
                    metricas['spotify_tracks_album_principal'] = tracks
                    metricas['spotify_top_tracks'] = [
                        {'titulo': t['titulo'], 'popularity': None,
                         'album': albums[0]['titulo'] if albums else '',
                         'url': t['url'], 'uri': t['uri']}
                        for t in tracks[:5]
                    ]
                    lst = listeners_from_page(info['id'])
                    if lst:
                        metricas['spotify_oyentes_mes'] = lst
                        metricas['spotify_oyentes_nota'] = f'~{lst} oyentes/mes (scrape público, {time.strftime("%Y-%m-%d")})'
                    metricas['spotify_fecha'] = time.strftime('%Y-%m-%d')
                    bands[band]['metricas'] = metricas
                    print(f'     → {len(albums)} álbumes, top {len(tracks[:5])} tracks del álbum principal')
                except Exception as e2:
                    print(f'  ⚠️ {band}: fallback catálogo también falló ({e2})')
            else:
                print(f'  ⚠️ {band}: {e}')
        except Exception as e:
            print(f'  ⚠️ {band}: {e}')

    BANDS_PATH.write_text(json.dumps(bands, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Guardado → {BANDS_PATH}')


if __name__ == '__main__':
    main()
