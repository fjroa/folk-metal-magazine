#!/usr/bin/env python3
"""folk_media_fetch.py — Descarga caché persistente de fotos (og:image) y logos (perfil IG).

Caché: <repo>/media/photos/{safe}_{shortcode}.jpg (400x300) y
       <repo>/media/logos/{safe}.png (200x200)
NUNCA usar /tmp: es efímero y degrada la revista cuando se limpia.
IMPORTANTE: secuencial + delay corto — Instagram rate-limita las ráfagas concurrentes
(probado: 8 workers → 233/233 fallos; secuencial → 100% éxito).
Uso: python3 scripts/folk_media_fetch.py [YYYY-MM]
"""
import os, re, sqlite3, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path('/home/roa/github/folk-metal-magazine')
MEDIA = REPO / 'media'
PHOTOS = MEDIA / 'photos'
LOGOS = MEDIA / 'logos'
DB = Path.home() / '.hermes' / 'folk_metal_posts.db'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
DELAY = 1.2

if len(sys.argv) > 1:
    MONTH = sys.argv[1]
else:
    _first = datetime.now().replace(day=1)
    MONTH = (_first - timedelta(days=1)).strftime('%Y-%m')

PHOTOS.mkdir(parents=True, exist_ok=True)
LOGOS.mkdir(parents=True, exist_ok=True)

def safe(band):
    return band.replace(' ', '_').replace('ä', 'a').replace('ë', 'e').replace('ö', 'o').replace('è', 'e').replace('ü', 'u')

def curl(url, out, timeout=20):
    try:
        subprocess.run(['curl', '-sL', '-o', str(out), '--max-time', str(timeout),
                        '-H', f'User-Agent: {UA}', url], capture_output=True, timeout=timeout + 10)
        return out.exists() and out.stat().st_size > 5000
    except Exception:
        return False

def og_image(post_url):
    for attempt in range(2):
        try:
            r = subprocess.run(['curl', '-sL', '--max-time', '15', '-H', f'User-Agent: {UA}', post_url],
                               capture_output=True, text=True, timeout=25)
            m = re.search(r'<meta property="og:image" content="([^"]+)"', r.stdout)
            if m:
                return m.group(1).replace('&amp;', '&')
            time.sleep(1.0)
        except Exception:
            time.sleep(1.0)
    return None

def to_jpg(path, out):
    try:
        # ImageMagick usa la extensión para elegir decoder: '.raw' lo interpreta
        # como DNG/cámara y falla aunque el contenido sea JPEG/WebP. Detectamos
        # el tipo real con `file` y renombramos con la extensión correcta.
        ft = subprocess.run(['file', '-b', str(path)], capture_output=True, text=True, timeout=10).stdout.lower()
        ext = '.webp' if 'webp' in ft else ('.png' if 'png' in ft else '.jpg')
        # Nombre intermedio ÚNICO: con_suffix('.jpg') colisionaría con `out`
        # (mismo {safe}_{shortcode}.jpg) y convert no puede leer/escribir el mismo fichero.
        tmp2 = path.with_name(path.stem + '_conv' + ext)
        if tmp2 != path:
            os.replace(str(path), str(tmp2))
        r = subprocess.run(['convert', str(tmp2), '-resize', '400x300^', '-gravity', 'center',
                            '-extent', '400x300', str(out)], capture_output=True, timeout=30)
        if tmp2 != path:
            tmp2.unlink(missing_ok=True)
        return out.exists() and out.stat().st_size > 5000
    except Exception:
        return False

def fetch_photo(shortcode, band, img_url, post_url):
    out = PHOTOS / f'{safe(band)}_{shortcode}.jpg'
    if out.exists() and out.stat().st_size > 5000:
        return 'skip'
    tmp = PHOTOS / f'{safe(band)}_{shortcode}.raw'
    if img_url and '/media?size=' not in img_url:
        if curl(img_url, tmp):
            if to_jpg(tmp, out):
                tmp.unlink(missing_ok=True)
                return 'ok'
    if post_url:
        cdn = og_image(post_url)
        if cdn and curl(cdn, tmp):
            if to_jpg(tmp, out):
                tmp.unlink(missing_ok=True)
                return 'ok'
    tmp.unlink(missing_ok=True)
    return 'fail'

def fetch_logo(band, handle):
    out = LOGOS / f'{safe(band)}.png'
    if out.exists() and out.stat().st_size > 1000:
        return 'skip'
    cdn = og_image(f'https://www.instagram.com/{handle}/') if handle else None
    if cdn:
        tmp = LOGOS / f'{safe(band)}.raw'
        if curl(cdn, tmp, timeout=15):
            subprocess.run(['convert', str(tmp), '-resize', '200x200^', '-gravity', 'center',
                            '-extent', '200x200', str(out)], capture_output=True, timeout=30)
            tmp.unlink(missing_ok=True)
            if out.exists() and out.stat().st_size > 1000:
                return 'ok'
    return 'fail'

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT shortcode, band_name, handle, image_url, post_url FROM posts WHERE post_date LIKE ?",
                        (MONTH + '%',)).fetchall()
    bands = {}
    for r in conn.execute("SELECT band_name, handle FROM posts WHERE post_date LIKE ? GROUP BY band_name", (MONTH + '%',)):
        bands[r['band_name']] = r['handle']
    conn.close()
    print(f'[{MONTH}] fotos={len(rows)} logos={len(bands)}', flush=True)

    ok = fail = skip = 0
    for r in rows:
        st = fetch_photo(r['shortcode'], r['band_name'], r['image_url'], r['post_url'])
        ok += st == 'ok'; fail += st == 'fail'; skip += st == 'skip'
        time.sleep(DELAY)
    print(f'fotos: ok={ok} fail={fail} skip={skip}', flush=True)

    l_ok = l_fail = l_skip = 0
    for b, h in bands.items():
        st = fetch_logo(b, h)
        l_ok += st == 'ok'; l_fail += st == 'fail'; l_skip += st == 'skip'
        time.sleep(DELAY)
    print(f'logos: ok={l_ok} fail={l_fail} skip={l_skip}', flush=True)

if __name__ == '__main__':
    main()
