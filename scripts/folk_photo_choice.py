#!/usr/bin/env python3
"""folk_photo_choice.py — Clasifica fotos de la caché: FOTO de la banda vs CARTEL.

Para cada banda, toma las N fotos más grandes de media/photos y pregunta a un
modelo de visión (OpenRouter gpt-4o-mini, barato) si la imagen muestra a la banda
(miembros, directo, estudio) o es un cartel/poster promocional (flyer, diseño
gráfico, texto grande). Guarda media/photo_choices_{MONTH}.json:
  { band: { shortcode: 'FOTO'|'CARTEL'|'DESCONOCIDO', file: ..., score: 1|0|0.5 } }

Uso: python3 scripts/folk_photo_choice.py [YYYY-MM] [--top N]
"""
import base64, glob, json, os, re, sqlite3, sys, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path('/home/roa/github/folk-metal-magazine')
MEDIA = REPO / 'media'
PHOTOS = MEDIA / 'photos'
DB = Path.home() / '.hermes' / 'folk_metal_posts.db'
OR_URL = 'https://openrouter.ai/api/v1/chat/completions'
OR_MODEL = 'openai/gpt-4o-mini'
TOP = 4  # fotos candidatas por banda (las más grandes)

if len(sys.argv) > 1:
    MONTH = sys.argv[1]
else:
    _first = datetime.now().replace(day=1)
    MONTH = (_first - timedelta(days=1)).strftime('%Y-%m')
if '--top' in sys.argv:
    TOP = int(sys.argv[sys.argv.index('--top') + 1])

MEDIA.mkdir(parents=True, exist_ok=True)

def safe(band):
    return band.replace(' ', '_').replace('ä', 'a').replace('ë', 'e').replace('ö', 'o').replace('è', 'e').replace('ü', 'u')

def or_key():
    try:
        txt = Path.home().joinpath('.hermes/.env').read_text()
        m = re.search(r'^OPENROUTER_API_KEY=(.*)$', txt, re.M)
        return m.group(1).strip() if m else ''
    except Exception:
        return ''

def classify(image_b64):
    body = json.dumps({
        'model': OR_MODEL,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': (
                'Clasifica esta imagen de una banda de folk metal español. '
                'Responde SOLO con una palabra: "FOTO" si es una foto real donde aparece la banda '
                '(miembros, concierto, directo, backstage, estudio, personas), o "CARTEL" si es un '
                'cartel/poster promocional (diseño gráfico, flyer de concierto, texto grande, logo, '
                'ilustración sin personas). Si no está claro, responde "DESCONOCIDO".')},
            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_b64}'}}
        ]}],
        'max_tokens': 10, 'temperature': 0
    }).encode()
    req = urllib.request.Request(OR_URL, data=body,
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': f'Bearer {or_key()}'})
    with urllib.request.urlopen(req, timeout=90) as resp:
        d = json.loads(resp.read().decode())
    return (d['choices'][0]['message']['content'] or '').strip().upper()

def main():
    # shortcode → banda (para saber el shortcode de cada fichero)
    conn = sqlite3.connect(DB)
    sc_map = {}
    for b, sc in conn.execute("SELECT band_name, shortcode FROM posts WHERE post_date LIKE ?", (MONTH + '%',)):
        sc_map.setdefault(safe(b), []).append(sc)
    conn.close()

    files = sorted(glob.glob(str(PHOTOS / '*.jpg')), key=os.path.getsize, reverse=True)
    by_band = {}
    for f in files:
        band = os.path.basename(f).rsplit('_', 1)[0]
        by_band.setdefault(band, []).append(f)

    choices = {}
    for band, flist in sorted(by_band.items()):
        cands = flist[:TOP]
        results = []
        for f in cands:
            b64 = base64.b64encode(Path(f).read_bytes()).decode()
            try:
                verdict = classify(b64)
            except Exception as e:
                print(f'  [warn] {os.path.basename(f)}: {e}')
                verdict = 'DESCONOCIDO'
            shortcode = None
            stem = os.path.basename(f)[:-4]
            for sc in sc_map.get(band, []):
                if stem.endswith(sc):
                    shortcode = sc
                    break
            results.append({'file': os.path.basename(f), 'shortcode': shortcode, 'verdict': verdict,
                            'score': 1 if verdict == 'FOTO' else (0.5 if verdict == 'DESCONOCIDO' else 0)})
            print(f'  {band}: {os.path.basename(f)} → {verdict}', flush=True)
        choices[band] = results

    out = MEDIA / f'photo_choices_{MONTH}.json'
    out.write_text(json.dumps(choices, ensure_ascii=False, indent=1), encoding='utf-8')
    # resumen
    tot_foto = sum(1 for r in choices.values() for x in r if x['verdict'] == 'FOTO')
    tot_cartel = sum(1 for r in choices.values() for x in r if x['verdict'] == 'CARTEL')
    print(f'\nOK: {out} | bandas={len(choices)} | FOTO={tot_foto} CARTEL={tot_cartel}')

if __name__ == '__main__':
    main()
