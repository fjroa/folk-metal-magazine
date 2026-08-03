#!/usr/bin/env python3
"""build_v16.py — Builder determinista de la revista HTML standalone.

python3 scripts/build_v16.py [YYYY-MM]   (por defecto, mes anterior)

Fuentes:
  - ~/.hermes/folk_metal_posts.db (posts, news_posts, concerts)
  - media/photos/{safe}_{shortcode}.jpg , media/logos/{safe}.png (caché local)
  - media/summaries_{MONTH}.json (editorial de LLM; si falta, regla por regla)

Salida: ediciones/YYYY-MM.html (imágenes base64 embebidas, estilo pergamino).
"""
import base64, calendar, html, json, os, re, sqlite3, sys, unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = Path.home() / '.hermes' / 'folk_metal_posts.db'
MEDIA = REPO / 'media'
PHOTOS = MEDIA / 'photos'
LOGOS = MEDIA / 'logos'
EDICIONES = REPO / 'ediciones'

if len(sys.argv) > 1:
    MONTH = sys.argv[1]
else:
    _first = datetime.now().replace(day=1)
    MONTH = (_first - timedelta(days=1)).strftime('%Y-%m')
EDICIONES.mkdir(parents=True, exist_ok=True)
OUT = EDICIONES / f'{MONTH}.html'

MONTH_NAMES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
month_date = datetime.strptime(MONTH, '%Y-%m')
month_name = MONTH_NAMES[month_date.month - 1].capitalize()
prev_month = (month_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')

CSS = '''
:root{scroll-behavior:smooth;--cream:#f5f0e8;--paper:#ede4d3;--dark:#2c1810;--text:#3d2b1f;--accent:#8b2500;--gold:#b8860b;--muted:#8c7b6b;--card:#faf6ef;--border:#d4c5a9;--highlight:#fff8e7}
*{box-sizing:border-box}body{margin:0;background:#e8dcc8;background-image:url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.08'/%3E%3C/svg%3E"),linear-gradient(180deg,#ede4d3,#d9ccb5);color:var(--text);font:15px/1.55 Georgia,'Times New Roman',serif}.cover{background:linear-gradient(160deg,#2c1810,#4a2820,#3d1f15,#2c1810);color:var(--gold);text-align:center;padding:80px 20px 60px;position:relative}.cover h1{font-size:clamp(38px,8vw,72px);letter-spacing:5px;margin:0}.cover .sub{color:#c9a84c;font-size:clamp(15px,3vw,22px);font-style:italic;margin:12px}.cover .meta{color:#a09080;font-size:13px;line-height:2}.cover .stats{display:flex;justify-content:center;gap:28px;flex-wrap:wrap;margin:28px 0 0}.cover strong{display:block;font-size:28px;color:var(--gold)}.container{max-width:1000px;margin:0 auto;padding:0 24px}@media(max-width:700px){.container{padding:0 12px}}.section-nav{display:flex;justify-content:center;gap:14px;flex-wrap:wrap;padding:20px 12px 8px;font-size:13px}.section-nav a{color:var(--accent);text-decoration:none}.section-nav a:hover{color:var(--gold)}.section-divider{text-align:center;padding:46px 0 20px}.section-divider h2{font-size:clamp(25px,4vw,40px);color:var(--accent);letter-spacing:2px;border-top:2px solid var(--border);border-bottom:2px solid var(--border);padding:20px;margin:0}.toc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:7px}.toc-card,.band-card,.hl-card,.news-card{background:var(--card);border:1px solid var(--border);border-radius:4px}.toc-card{padding:9px;text-align:center}.toc-card img{width:32px;height:32px;display:block;margin:0 auto 4px}.toc-card a{color:var(--accent);text-decoration:none;font-size:13px}.toc-num{font-size:10px;color:var(--muted);display:block}.lead{color:var(--muted);font-size:13px;text-align:center;margin:0 auto 18px;max-width:760px}.hl-list{display:grid;gap:9px}.hl-card{display:flex;overflow:hidden}.hl-card img{width:100px;height:92px;object-fit:cover;flex:0 0 auto;background:var(--dark)}.hl-body{padding:10px 14px}.hl-band{color:var(--accent);font-size:14px}.hl-text{font-size:13px;margin-top:4px}.calendar{max-width:960px;margin:auto}.cal-head,.cal-row{display:grid;grid-template-columns:repeat(7,1fr)}.cal-head div{padding:8px;text-align:center;color:var(--gold);font-size:12px;border-bottom:1px solid var(--border)}.cal-cell{min-height:112px;padding:6px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);background:rgba(250,246,239,.55)}.cal-cell:nth-child(7n){border-right:0}.cal-empty{background:rgba(237,228,211,.4)}.cal-day{font-size:12px;color:var(--accent);font-weight:bold}.cal-event{font-size:10px;line-height:1.25;margin-top:5px}.cal-event a{color:var(--accent);text-decoration:none}.band-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}.band-card-wrapper{position:relative}.top-link{position:absolute;right:9px;top:7px;color:var(--accent);font-size:11px;text-decoration:none;opacity:.5}.band-card{overflow:hidden}.band-header{display:flex;gap:12px;padding:12px;border-bottom:1px solid #f0ebe0;align-items:center}.band-header img{width:74px;height:74px;border-radius:4px}.band-header .name{font-size:17px;color:var(--accent)}.metrics{font-size:11px;color:var(--muted);margin-top:3px}.count{font-size:10px;color:var(--muted)}.band-summary{padding:10px 12px;font-size:12.5px;font-style:italic;border-bottom:1px solid #f0ebe0}.post-item{padding:8px 12px;border-bottom:1px solid #eee5d7;font-size:12px}.post-date{color:var(--gold);font-size:10px;margin-right:8px}.post-link{float:right}.post-link a{color:var(--accent);text-decoration:none;font-size:14px}.collapsed{display:none}.more-row{cursor:pointer;text-align:center;color:var(--accent);font-size:11px;font-style:italic;padding:8px}.more-row:hover{background:var(--highlight)}.news-list{display:grid;gap:7px;max-width:900px;margin:auto}.news-card{padding:9px 12px;font-size:12px}.news-card a{color:var(--accent);text-decoration:none}.news-source{color:var(--muted);font-size:10px}.metrics-table{width:100%;border-collapse:collapse;font-size:12px}.metrics-table th,.metrics-table td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--border)}.metrics-table th{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px}.metrics-table tr:hover td{background:var(--highlight)}.up{color:#287a3e}.down{color:#a52c1c}.flat{color:var(--muted)}footer{text-align:center;padding:45px 20px;color:var(--muted);font-size:11px}footer a{color:var(--accent);text-decoration:none}
'''


def esc(x):
    return html.escape(str(x or ''), quote=True)


def clean_caption(text):
    text = text or ''
    replacements = [
        (r'&\s*#039\s*;', "'"), (r'&\s*#8217\s*;', "'"),
        (r'&\s*#39\s*;', "'"), (r'&\s*amp\s*;', '&'),
        (r'&\s*quot\s*;', '"'),
    ]
    for pat, repl in replacements:
        text = re.sub(pat, repl, text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


def safe(band):
    return band.replace(' ', '_').replace('ä', 'a').replace('ë', 'e')\
               .replace('ö', 'o').replace('è', 'e').replace('ü', 'u')


def eid(name):
    # Anclas: quita diéresis /tildes propias de esas vocales, conserva áéíóúñ.
    s = name.lower().strip()
    dia = {'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u', 'ÿ': 'y', 'è': 'e'}
    out = ''.join(dia.get(ch, ch) for ch in s)
    return re.sub(r'[^a-z0-9áéíóúñ]+', '-', out).strip('-')


def svg_data(name, size=220):
    initial = html.escape((name.strip() or '?')[0].upper())
    esc_name = html.escape(name)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
           f'viewBox="0 0 {size} {size}"><rect width="100%" height="100%" fill="#2c1810"/>'
           f'<circle cx="{size/2}" cy="{size/2}" r="{size*.34}" fill="#8b2500" '
           f'stroke="#b8860b" stroke-width="5"/>'
           f'<text x="50%" y="56%" text-anchor="middle" font-family="Georgia,serif" '
           f'font-size="{size*.32}" fill="#f5f0e8">{initial}</text>'
           f'<title>{esc_name}</title></svg>')
    return base64.b64encode(svg.encode()).decode()


def logo_b64(band):
    path = LOGOS / f'{safe(band)}.png'
    if path.exists() and path.stat().st_size > 1000:
        return 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()
    # Fallback: mejor foto de la banda (IG ya no expone la foto de perfil vía og:image
    # ni profile_pic_url; una foto real queda mejor que una inicial).
    cands = sorted(PHOTOS.glob(f'{safe(band)}_*.jpg'),
                   key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    if cands and cands[0].stat().st_size > 5000:
        return 'data:image/jpeg;base64,' + base64.b64encode(cands[0].read_bytes()).decode()
    return 'data:image/svg+xml;base64,' + svg_data(band)


def photo_b64(band, shortcode):
    path = PHOTOS / f'{safe(band)}_{shortcode}.jpg'
    if path.exists() and path.stat().st_size > 5000:
        return 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode()
    return logo_b64(band)


def best_photo_b64(band):
    cands = sorted(PHOTOS.glob(f'{safe(band)}_*.jpg'),
                   key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    if cands and cands[0].stat().st_size > 5000:
        return 'data:image/jpeg;base64,' + base64.b64encode(cands[0].read_bytes()).decode()
    return logo_b64(band)


def parse_metric(v):
    v = (v or '').replace(',', '').strip().upper()
    if v in ('', '—', '-'):
        return -1
    try:
        if v.endswith('M'):
            return float(v[:-1]) * 1_000_000
        if v.endswith('K'):
            return float(v[:-1]) * 1_000
        return float(v)
    except ValueError:
        return -1


def rule_summary(band, rows):
    text = ' '.join(clean_caption(r['caption']) for r in rows).lower()
    facts = []
    if re.search(r'álbum|album|disco|single|estren|lanz|grabaci|producc', text):
        facts.append('La actividad incluyó referencias a lanzamientos o a nuevo material.')
    if re.search(r'festival|concierto|directo|gira|escenario|sala ', text):
        facts.append('También comunicó fechas de directo, festivales o actividad de gira.')
    if re.search(r'méxico|mexico|argentina|colombia|italia|europa|internacional', text):
        facts.append('Parte de la comunicación tuvo dimensión internacional.')
    if not facts:
        facts.append('La banda mantuvo actividad en redes con contenido visual y promocional.')
    if len(facts) == 1:
        facts.append('La ficha enlaza cada publicación original para facilitar la comprobación de los datos.')
    return ' '.join(facts[:2])


# Highlights con emoji por banda (copiado de folk_editorial HIGHLIGHT_SPECS para el fallback).
HIGHLIGHT_SPECS = [
    ('Nidhögg', '💀', [r'se retira|retirada|adiós definitivo|último disco']),
    ('Argion', '🌊', [r'sobre el mar|vltreia|single|adelanto']),
    ('Dark Moor', '💿', [r'doble cd|recopilatorio|edición limitada|25 aniversario|formación especial']),
    ('Saurom', '⚔️', [r'nuevo (disco|álbum|single)|adelanto|estren|grabaci|leyendas del rock']),
    ('Celtian', '🎼', [r'disco en directo|desde las raíces|maleficio|adelanto|la riviera']),
    ('Mägo de Oz', '🐉', [r'nuevo (disco|álbum|single)|adelanto|estren|gira internacional|wacken|rock imperium']),
    ('Lèpoka', '🍺', [r'nuevo (disco|álbum|single)|adelanto|estren|grabaci|leyendas del rock']),
    ('Ekyrian', '🌊', [r'leyendas del rock|nuevo (disco|álbum|single)|adelanto']),
    ('Hadadanza', '🔥', [r'leyendas del rock|nuevo (disco|álbum|single)|adelanto']),
    ('Reino de Hades', '⚒️', [r'nuevo (disco|álbum|single)|adelanto|grabaci|leyendas del rock|festival']),
    ('Salduie', '🏹', [r'nuevo (disco|álbum|single)|adelanto|grabaci|leyendas del rock']),
    ('Kinnia', '⚡', [r'nuevo (disco|álbum|single)|adelanto|grabaci|leyendas del rock']),
    ('Triskel', '🏴', [r'nuevo (disco|álbum|single)|adelanto|grabaci|rock imperium']),
    ('Celtibeerian', '🛡️', [r'nuevo (disco|álbum|single)|adelanto|grabaci|feffarkhorn']),
]


def build_highlights_fallback(bands, posts):
    highlights = []
    seen = set()
    for h_band, emoji, kws in HIGHLIGHT_SPECS:
        if h_band not in bands or h_band in seen:
            continue
        for kw in kws:
            matched = None
            for p in posts:
                if p['band_name'] != h_band:
                    continue
                if re.search(kw, clean_caption(p['caption']), re.I):
                    matched = p
                    break
            if matched:
                cap = clean_caption(matched['caption'])
                excerpt = cap[:357].rsplit(' ', 1)[0] + '…' if len(cap) > 360 else cap
                url = matched['post_url'] or f'https://www.instagram.com/p/{matched["shortcode"]}/'
                highlights.append({'band': h_band, 'emoji': emoji, 'text': excerpt,
                                   'post_url': url, 'shortcode': matched['shortcode']})
                seen.add(h_band)
                break
    return highlights


METRIC_DEFAULTS = {
    'Mägo de Oz': ('3.8M', '3.7M', '▲', 'up'),
    'Saurom': ('254.8K', '271.9K', '▼', 'down'),
    'Salduie': ('152.9K', '141.9K', '▲', 'up'),
    'Celtian': ('131.6K', '147.2K', '▼', 'down'),
    'Lèpoka': ('109.8K', '101.4K', '▲', 'up'),
    'Debler': ('78.9K', '74.5K', '▲', 'up'),
    'Dark Moor': ('71.6K', '—', '—', 'flat'),
    'Ekyrian': ('35.7K', '34.2K', '▲', 'up'),
    'El Reno Renardo': ('29.3K', '29.3K', '→', 'flat'),
    'Hadadanza': ('26.3K', '26.3K', '→', 'flat'),
    'Lándevir': ('14.3K', '14.3K', '→', 'flat'),
    'Celtibeerian': ('14.1K', '3.0K', '▲', 'up'),
    'Kinnia': ('9.9K', '9.9K', '→', 'flat'),
    'Daeria': ('8.2K', '—', '—', 'flat'),
    'Finnway': ('6.4K', '6.4K', '→', 'flat'),
    'Sovengar': ('4.0K', '4.0K', '→', 'flat'),
    'Argion': ('3.1K', '—', '—', 'flat'),
    'Dünedain': ('2.5K', '—', '—', 'flat'),
    'Reino de Hades': ('1.9K', '1.9K', '→', 'flat'),
    'Xeria': ('1.6K', '—', '—', 'flat'),
    'Triskel': ('1.1K', '1.1K', '→', 'flat'),
    'Kaelis': ('890', '—', '—', 'flat'),
    'Khëleden': ('762', '762', '→', 'flat'),
    'Nidhögg': ('332', '332', '→', 'flat'),
    'Trovadorum': ('101', '101', '→', 'flat'),
}


def load_metrics(band_names):
    metrics = {}
    src = EDICIONES / f'{prev_month}.html'
    if src.exists():
        text = src.read_text(errors='ignore')
        pat = re.compile(
            r'<tr><td class="rank">\d+</td><td class="band-name">(.*?)</td>'
            r'<td><strong>(.*?)</strong></td>'
            r'<td style="color:var\(--muted\)">(.*?)</td>'
            r'<td><span class="([^"]+)">(.*?)</span></td></tr>')
        for band, now, q2, cls, arrow in pat.findall(text):
            metrics[html.unescape(band)] = (html.unescape(now), html.unescape(q2),
                                            html.unescape(arrow), cls)
    if not metrics:
        metrics = dict(METRIC_DEFAULTS)
    return metrics


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
posts = conn.execute(
    '''SELECT band_name, handle, shortcode, post_date, caption, image_url, post_url
       FROM posts WHERE post_date LIKE ?
       ORDER BY band_name COLLATE NOCASE, post_date DESC, id DESC''',
    (MONTH + '%',)).fetchall()
news = conn.execute(
    '''SELECT source, title, url, published FROM news_posts WHERE published LIKE ?
       ORDER BY published DESC LIMIT 12''',
    (MONTH + '%',)).fetchall()
concert_rows = conn.execute(
    '''SELECT date, band_name, event_name, event_type, city, venue, source_url
       FROM concerts WHERE date LIKE ? AND band_name != 'Medio'
       ORDER BY date, band_name''',
    (MONTH + '%',)).fetchall()
conn.close()

bands = defaultdict(list)
for p in posts:
    bands[p['band_name']].append(p)
band_names = sorted(bands, key=lambda s: s.casefold())

# Editorial: summaries + highlights desde JSON si existe, fallback por regla.
summaries_path = MEDIA / f'summaries_{MONTH}.json'
summaries_data = {}
if summaries_path.exists():
    try:
        summaries_data = json.loads(summaries_path.read_text(encoding='utf-8'))
    except Exception:
        summaries_data = {}
summaries_txt = summaries_data.get('summaries', {}) or {}
highlights = summaries_data.get('highlights', []) if summaries_data else []
if not highlights:
    highlights = build_highlights_fallback(set(bands), posts)

# Calendario.
events = defaultdict(list)
for r in concert_rows:
    events[r['date']].append(r)
first = month_date.date().replace(day=1)
last_day = calendar.monthrange(month_date.year, month_date.month)[1]
start_offset = first.weekday()  # lunes-first


def event_label(r):
    parts = []
    if r['event_name']:
        parts.append(r['event_name'])
    if r['city']:
        parts.append(r['city'])
    if r['venue']:
        parts.append(r['venue'])
    return ' — '.join(parts) if parts else 'Fecha anunciada'


def event_icon(t):
    return {'festival': '🎪', 'gira': '🗺️', 'concierto': '🎸'}.get(t or '', '🎸')


metrics = load_metrics(band_names)

parts = ['<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
         f'<title>Folk Metal Magazine · {month_name} {month_date.year}</title>',
         f'<style>{CSS}</style></head><body>']

# 1. Portada
parts.append(
    f'<header class="cover">'
    f'<h1>FOLK METAL<br>MAGAZINE</h1>'
    f'<div class="sub">Edición mensual · {month_name} {month_date.year}</div>'
    f'<div class="meta">Escena folk metal española · datos verificables desde publicaciones y RSS<br>'
    f'RSS Bridge + Instagram + medios especializados</div>'
    f'<div class="stats">'
    f'<div><strong>{len(posts)}</strong> publicaciones</div>'
    f'<div><strong>{len(band_names)}</strong> bandas</div>'
    f'<div><strong>{len(news)}</strong> noticias</div>'
    f'</div></header>')

# 2. Nav
parts.append(
    '<nav class="section-nav">'
    '<a href="#indice">Índice</a><span>·</span>'
    '<a href="#gordo">🔥 Lo Gordo</a><span>·</span>'
    '<a href="#agenda">📅 Agenda</a><span>·</span>'
    '<a href="#bandas">⚔️ Bandas</a><span>·</span>'
    '<a href="#radar">📰 Radar</a><span>·</span>'
    '<a href="#metricas">📊 Métricas</a></nav>')

parts.append('<main class="container">')

# 3. Índice
parts.append('<section id="indice"><div class="section-divider"><h2>Índice de Bandas</h2></div>')
parts.append('<div class="toc-grid">')
for i, band in enumerate(band_names, 1):
    parts.append(f'<div class="toc-card"><a href="#b-{eid(band)}">'
                 f'<img src="{logo_b64(band)}" alt="Logo {esc(band)}">'
                 f'<span class="toc-num">#{i:02d}</span>{esc(band)}</a></div>')
parts.append('</div></section>')

# 4. Lo Gordo
parts.append('<section id="gordo"><div class="section-divider"><h2>🔥 Lo Gordo del Mes</h2></div>')
parts.append('<p class="lead">Selección de publicaciones del periodo con lanzamientos, novedades de formación, '
             'giras y anuncios relevantes. Cada texto procede de una publicación enlazada.</p>')
parts.append('<div class="hl-list">')
for h in highlights:
    img = photo_b64(h['band'], h.get('shortcode', ''))
    text = clean_caption(h.get('text') or '')
    if len(text) > 360:
        text = text[:357].rsplit(' ', 1)[0] + '…'
    parts.append(
        f'<article class="hl-card"><img src="{img}" alt="Foto {esc(h["band"])}">'
        f'<div class="hl-body"><div class="hl-band">{h.get("emoji", "🔥")} {esc(h["band"])}</div>'
        f'<div class="hl-text">{esc(text)} '
        f'<a href="{esc(h["post_url"])}" target="_blank" rel="noopener">🔗</a></div></div></article>')
if not highlights:
    parts.append('<p class="lead">No hubo publicaciones que cumplieron los criterios de selección.</p>')
parts.append('</div></section>')

# 5. Agenda
parts.append('<section id="agenda"><div class="section-divider"><h2>📅 Agenda de Conciertos</h2></div>')
parts.append('<p class="lead">Agenda estructurada a partir de eventos detectados en la base de datos del periodo.</p>')
parts.append('<div class="calendar"><div class="cal-head">' +
             ''.join(f'<div>{d}</div>' for d in ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do']) + '</div>')
for cell_index in range(start_offset + last_day):
    if cell_index % 7 == 0:
        parts.append('<div class="cal-row">')
    day_num = cell_index - start_offset + 1
    if day_num < 1 or day_num > last_day:
        parts.append('<div class="cal-cell cal-empty"></div>')
    else:
        date_key = f'{MONTH}-{day_num:02d}'
        ev_html = []
        for r in events.get(date_key, []):
            label = event_label(r)
            link = r['source_url'] or '#'
            ev_html.append(f'<div class="cal-event">{event_icon(r["event_type"])} {esc(r["band_name"])}<br>'
                           f'<a href="{esc(link)}" target="_blank" rel="noopener">{esc(label)} 🔗</a></div>')
        parts.append(f'<div class="cal-cell"><div class="cal-day">{day_num}</div>{"".join(ev_html)}</div>')
    if cell_index % 7 == 6:
        parts.append('</div>')
if (start_offset + last_day) % 7:
    for _ in range(7 - ((start_offset + last_day) % 7)):
        parts.append('<div class="cal-cell cal-empty"></div>')
    parts.append('</div>')
parts.append('</div></section>')

# 6. Todas las Bandas
parts.append('<section id="bandas"><div class="section-divider"><h2>⚔️ Todas las Bandas</h2></div>')
parts.append('<div class="band-grid">')
for band in band_names:
    rows = bands[band]
    metric = metrics.get(band)
    metric_html = ''
    if metric:
        now, q2, arrow, cls = metric
        metric_html = f'<div class="metrics">🎧 {esc(now)} <span class="{esc(cls)}">{esc(arrow)}</span> ' \
                      f'<span class="count">Q2: {esc(q2)}</span></div>'
    summary_txt = summaries_txt.get(band) or rule_summary(band, rows)
    parts.append(f'<article class="band-card-wrapper" id="b-{eid(band)}">'
                 f'<a class="top-link" href="#indice">↑ índice</a>'
                 f'<div class="band-card"><div class="band-header">'
                 f'<img src="{best_photo_b64(band)}" alt="Foto {esc(band)}">'
                 f'<div><div class="name">{esc(band)}</div>{metric_html}'
                 f'<div class="count">{len(rows)} publicaciones</div></div></div>'
                 f'<div class="band-summary">{esc(summary_txt)}</div>')
    for idx, p in enumerate(rows):
        cap = clean_caption(p['caption'])
        if len(cap) > 360:
            cap = cap[:357].rsplit(' ', 1)[0] + '…'
        klass = 'post-item' + (' collapsed' if idx >= 3 else '')
        date = (p['post_date'] or '')[:10]
        link = p['post_url'] or f'https://www.instagram.com/p/{p["shortcode"]}/'
        parts.append(f'<div class="{klass}"><span class="post-date">{esc(date)}</span>{esc(cap)} '
                     f'<span class="post-link"><a href="{esc(link)}" target="_blank" rel="noopener">🔗</a></span></div>')
    if len(rows) > 3:
        parts.append(f'<div class="more-row">▼ ver todas ({len(rows)} publicaciones)</div>')
    parts.append('</div></article>')
parts.append('</div></section>')

# 7. Radar de Medios
parts.append('<section id="radar"><div class="section-divider"><h2>📰 Radar de Medios</h2></div>')
parts.append('<p class="lead">Muestra de artículos RSS incorporados durante el periodo; el acumulador conserva el histórico completo.</p>')
parts.append('<div class="news-list">')
for n in news:
    title = clean_caption(n['title'])
    parts.append(f'<article class="news-card"><span class="news-source">{esc(n["source"])} · '
                 f'{esc((n["published"] or "")[:10])}</span><br>'
                 f'<a href="{esc(n["url"])}" target="_blank" rel="noopener">{esc(title)}</a></article>')
parts.append('</div></section>')

# 8. Métricas
parts.append('<section id="metricas"><div class="section-divider"><h2>📊 Métricas Spotify</h2></div>')
parts.append('<p class="lead">Último snapshot disponible del informe anterior; se conserva la escala numérica correcta '
             '(M &gt; K). Sin dato, se muestra «—».</p>')
parts.append('<table class="metrics-table"><thead><tr><th>#</th><th>Banda</th><th>Oyentes</th><th>Q2</th><th>Δ</th></tr></thead><tbody>')
metric_bands = sorted(set(band_names) | set(metrics),
                      key=lambda b: (-parse_metric(metrics.get(b, ('—', '—', '—', 'flat'))[0]), b.casefold()))
for i, band in enumerate(metric_bands, 1):
    now, q2, arrow, cls = metrics.get(band, ('—', '—', '→', 'flat'))
    parts.append(f'<tr><td class="rank">{i:02d}</td><td class="band-name">{esc(band)}</td>'
                 f'<td><strong>{esc(now)}</strong></td><td style="color:var(--muted)">{esc(q2)}</td>'
                 f'<td><span class="{esc(cls)}">{esc(arrow)}</span></td></tr>')
parts.append('</tbody></table></section>')

# 9. Footer
parts.append(f'</main><footer><a href="#indice">↑ Volver al índice</a><br><br>'
             f'Folk Metal Magazine · {month_name} {month_date.year}<br>'
             f'{len(posts)} publicaciones de Instagram · {len(news)} noticias RSS mostradas · '
             f'contenido enlazado a sus fuentes originales</footer>')

parts.append('<script>document.querySelectorAll(".more-row").forEach(function(btn){'
             'btn.addEventListener("click",function(){{'
             'var card=this.parentElement;'
             'var hidden=card.querySelectorAll(".post-item.collapsed");'
             'if(hidden.length){{'
             'hidden.forEach(function(x){{x.classList.remove("collapsed")}});'
             'this.textContent="▲ solo destacadas"'
             '}}else{{'
             'card.querySelectorAll(".post-item").forEach(function(x,i){{if(i>=3)x.classList.add("collapsed")}});'
             'this.textContent="▼ ver todas ("+card.querySelectorAll(".post-item").length+" publicaciones)"'
             '}}})}});</script>')
parts.append('</body></html>')

OUT.write_text(''.join(parts), encoding='utf-8')
print(f'Generated {OUT} | posts={len(posts)} bands={len(band_names)} '
      f'news={len(news)} events={len(concert_rows)} bytes={OUT.stat().st_size}')
