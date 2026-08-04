#!/usr/bin/env python3
"""spotify_auth.py — OAuth Authorization Code (con tu cuenta) para acceso completo.

Uso en dos pasos:
  1. python3 scripts/spotify_auth.py --url   → imprime la URL de autorización
  2. Abre la URL, aprueba, Spotify redirige a http://localhost:8888/callback?code=XXX
     (si no hay servidor local, copia el code de la URL del navegador)
  3. python3 scripts/spotify_auth.py --code XXX   → guarda refresh_token en ~/.hermes/.env

Requisitos: en el dashboard de la app, añadir TU cuenta de Spotify en
User Management (Settings → User Management → Add). La redirect URI
http://localhost:8888/callback debe estar registrada en la app.
"""
import base64, json, os, secrets, sys, urllib.parse, urllib.request
from pathlib import Path

ENV = Path.home() / '.hermes' / '.env'
# Redirect URI registrada en la app (Settings → Redirect URIs): con path /callback.
REDIRECT = 'http://127.0.0.1:8888/callback'
SCOPES = 'user-read-private user-read-email'


def creds():
    env = ENV.read_text() if ENV.exists() else ''
    def g(k):
        for line in env.splitlines():
            if line.startswith(k + '='):
                return line.split('=', 1)[1].strip()
        return ''
    return g('SPOTIFY_CLIENT_ID'), g('SPOTIFY_CLIENT_SECRET')


def auth_url():
    cid, _ = creds()
    state = secrets.token_urlsafe(16)
    params = urllib.parse.urlencode({
        'client_id': cid,
        'response_type': 'code',
        'redirect_uri': REDIRECT,
        'scope': SCOPES,
        'state': state,
    })
    print('Abre esta URL en tu navegador (con la cuenta de Spotify añadida a la app):')
    print()
    print('https://accounts.spotify.com/authorize?' + params)
    print()
    print('Después de aprobar, serás redirigido a algo como:')
    print(f'  {REDIRECT}?code=XXX&state={state}')
    print('Copia el valor de code= y ejecuta:')
    print('  python3 scripts/spotify_auth.py --code XXX')


def exchange(code):
    cid, csec = creds()
    auth = base64.b64encode(f'{cid}:{csec}'.encode()).decode()
    body = urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT,
    }).encode()
    req = urllib.request.Request('https://accounts.spotify.com/api/token', data=body, headers={
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    refresh = data.get('refresh_token', '')
    if not refresh:
        print('ERROR: no refresh_token en la respuesta. ¿La cuenta está añadida a la app?')
        print('Respuesta:', json.dumps(data)[:200])
        return
    # Guardar en .env (sin duplicar)
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    lines = [l for l in lines if not l.startswith('SPOTIFY_REFRESH_TOKEN=')]
    lines.append(f'SPOTIFY_REFRESH_TOKEN={refresh}')
    ENV.write_text('\n'.join(lines) + '\n')
    print(f'✅ refresh_token guardado en {ENV}')
    print('Ahora ejecuta: python3 scripts/band_metrics_spotify.py --user')


def main():
    if '--url' in sys.argv:
        auth_url()
    elif '--code' in sys.argv:
        exchange(sys.argv[sys.argv.index('--code') + 1])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
