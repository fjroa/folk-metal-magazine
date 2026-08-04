#!/usr/bin/env python3
"""build_band_historias.py — Fichas históricas por banda (capa profunda).

Genera historias/{slug}.html para cada banda + historias/index.html (índice).
La revista mensual es la capa accesible; ESTAS fichas son la profundidad:
histórico mes a mes, TODOS los conciertos, prensa, discografía, componentes,
sello, estudios, hitos y conexiones.

Fuentes:
  - ~/.hermes/folk_metal_posts.db (posts, news_posts, concerts — histórico completo)
  - data/band_profiles.json (datos curados verificados; vacíos = pendiente)
  - media/summaries_*.json (editorial LLM por mes, si existe)

Salida: historias/{slug}.html + historias/index.html (standalone, estilo pergamino).

Uso: python3 scripts/build_band_historias.py
"""
import base64, html, json, re, sqlite3, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = Path.home() / '.hermes' / 'folk_metal_posts.db'
MEDIA = REPO / 'media'
PHOTOS = MEDIA / 'photos'
LOGOS = MEDIA / 'logos'
HISTORIAS = REPO / 'historias'
INDEX = REPO / 'index.html'
# Fuente de datos unificada (futuro panel admin): data/bands.json (merge de
# band_profiles + band_briefs). Fallback a band_profiles si aún no existe.
_BANDS_PATH = REPO / 'data' / 'bands.json'
if _BANDS_PATH.exists():
    PROFILES = json.loads(_BANDS_PATH.read_text(encoding='utf-8'))
else:
    PROFILES = json.loads((REPO / 'data' / 'band_profiles.json').read_text(encoding='utf-8'))
    PROFILES = PROFILES.get('bands', PROFILES)  # tolera wrapper
PROFILES = {k: v for k, v in PROFILES.items() if k != 'meta'}

MONTH_NAMES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def esc(x):
    return html.escape(str(x or ''), quote=True)


def clean_caption(text):
    text = text or ''
    for pat, repl in [(r'&\s*#039\s*;', "'"), (r'&\s*#8217\s*;', "'"),
                      (r'&\s*#39\s*;', "'"), (r'&\s*amp\s*;', '&'),
                      (r'&\s*quot\s*;', '"')]:
        text = re.sub(pat, repl, text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


def safe(band):
    return band.replace(' ', '_').replace('ä', 'a').replace('ë', 'e') \
               .replace('ö', 'o').replace('è', 'e').replace('ü', 'u')


def slug(band):
    s = band.lower().strip()
    dia = {'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u', 'ÿ': 'y', 'è': 'e',
           'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
    s = ''.join(str(dia.get(ch, ch)) for ch in s)
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


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
    cands = sorted(PHOTOS.glob(f'{safe(band)}_*.jpg'),
                   key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    if cands and cands[0].stat().st_size > 5000:
        return 'data:image/jpeg;base64,' + base64.b64encode(cands[0].read_bytes()).decode()
    return 'data:image/svg+xml;base64,' + svg_data(band)


def best_photo_b64(band):
    cands = sorted((p for p in PHOTOS.glob(f'{safe(band)}_*.jpg') if p.stat().st_size > 5000),
                   key=lambda p: p.stat().st_size, reverse=True)
    if cands:
        return 'data:image/jpeg;base64,' + base64.b64encode(cands[0].read_bytes()).decode()
    return logo_b64(band)


def month_label(ym):
    try:
        d = datetime.strptime(ym, '%Y-%m')
        return f'{MONTH_NAMES[d.month - 1].capitalize()} {d.year}'
    except ValueError:
        return ym


CSS = '''
:root{scroll-behavior:smooth;--cream:#f5f0e8;--paper:#ede4d3;--dark:#2c1810;--text:#3d2b1f;--accent:#8b2500;--gold:#b8860b;--muted:#8c7b6b;--card:#faf6ef;--border:#d4c5a9;--highlight:#fff8e7}
*{box-sizing:border-box}body{margin:0;background:#e8dcc8;background-image:url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.08'/%3E%3C/svg%3E"),linear-gradient(180deg,#ede4d3,#d9ccb5);color:var(--text);font:15.5px/1.6 Georgia,'Times New Roman',serif}
.cover{background:linear-gradient(160deg,#2c1810,#4a2820,#3d1f15,#2c1810);color:var(--gold);text-align:center;padding:64px 20px 48px;position:relative;overflow:hidden}
.cover:after{content:'✦';position:absolute;inset:14px;border:1px solid rgba(184,134,11,.35);color:rgba(201,168,76,.5);font-size:16px;text-align:left;padding:8px;pointer-events:none}
.cover h1{font-size:clamp(34px,6vw,58px);letter-spacing:4px;margin:0;font-weight:normal}
.cover .sub{color:#c9a84c;font-style:italic;margin:10px;font-size:clamp(14px,2.5vw,20px)}
.cover .meta{color:#a09080;font-size:13px;line-height:1.9}
.cover .stats{display:flex;justify-content:center;gap:22px;flex-wrap:wrap;margin:24px 0 0}
.cover strong{display:block;font-size:26px;color:var(--gold)}
.container{max-width:1080px;margin:0 auto;padding:0 24px}@media(max-width:700px){.container{padding:0 12px}}
.section-nav{position:sticky;top:0;z-index:5;background:rgba(245,240,232,.94);border-bottom:1px solid var(--border);display:flex;justify-content:center;gap:14px;flex-wrap:wrap;padding:14px 12px;font-size:13px;letter-spacing:.4px}
.section-nav a{color:var(--accent);text-decoration:none}.section-nav a:hover{color:var(--gold)}
.section-divider{text-align:center;padding:44px 0 18px}
.section-divider h2{font-size:clamp(22px,3.5vw,34px);color:var(--accent);letter-spacing:2px;text-transform:uppercase;border:0;padding:0 0 14px;margin:0;position:relative}
.section-divider h2:after{content:'';display:block;width:100%;height:3px;margin-top:14px;background:linear-gradient(90deg,transparent,var(--gold),transparent);opacity:.7}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;box-shadow:0 5px 15px rgba(61,43,31,.08);padding:20px 22px;margin:14px 0}
.quick-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:14px 0}
.quick{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px 16px}
.quick b{display:block;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);margin-bottom:5px}
.quick span{color:var(--text)}
ul.clean{list-style:none;margin:8px 0;padding:0}
ul.clean li{padding:8px 4px;border-bottom:1px solid rgba(212,197,169,.6)}
ul.clean li:last-child{border-bottom:0}
.timeline{position:relative;margin:18px 0 6px;padding-left:26px}
.timeline:before{content:'';position:absolute;left:7px;top:4px;bottom:4px;width:2px;background:linear-gradient(180deg,var(--gold),var(--border))}
.tl-item{position:relative;margin:0 0 22px}
.tl-item:before{content:'';position:absolute;left:-23px;top:6px;width:12px;height:12px;border-radius:50%;background:var(--accent);border:2px solid var(--gold)}
.tl-month{font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold);font-weight:bold}
.tl-body{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-top:6px;box-shadow:0 3px 10px rgba(61,43,31,.06)}
.tl-tags{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 8px}
.tl-tag{font:700 10px ui-sans-serif,system-ui,sans-serif;padding:2px 8px;border-radius:20px;background:#ead6a2;color:#725100;letter-spacing:.4px;text-transform:uppercase}
.tl-post{font-size:13.5px;line-height:1.55;color:#3b2a20;padding:6px 0;border-bottom:1px dashed rgba(212,197,169,.5)}
.tl-post:last-child{border-bottom:0}
.tl-post .post-date{font-size:11px;color:#594637;font-weight:bold;margin-right:6px}
.tl-post a{color:var(--accent);text-decoration:none}
table.events{width:100%;border-collapse:collapse;margin:14px 0;background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden;box-shadow:0 5px 15px rgba(61,43,31,.08)}
table.events th{background:var(--dark);color:#f5f0e8;font-size:12px;letter-spacing:1px;text-transform:uppercase;padding:10px 12px;text-align:left}
table.events td{padding:10px 12px;border-top:1px solid rgba(212,197,169,.6);font-size:14.5px;vertical-align:top}
table.events tr.past td{color:var(--muted)}
table.events tr.future td{background:var(--highlight)}
table.events tr:hover td{background:#fff8e7}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font:700 10px ui-sans-serif,system-ui,sans-serif;letter-spacing:.4px;text-transform:uppercase;vertical-align:middle;margin-left:6px}
.badge-past{background:#e3ddd0;color:#6b5d4e}
.badge-future{background:#c6d8c2;color:#31553a}
.badge-news{background:#f2c6a8;color:#7c2b0a}
.badge-status{background:#ead6a2;color:#725100}
.news-card{border-left:4px solid var(--accent);padding:12px 16px;margin:8px 0;background:var(--card);border:1px solid var(--border);border-radius:6px;border-left-width:4px}
.news-card a{color:var(--accent);font-size:15.5px;text-decoration:none}
.news-card a:hover{text-decoration:underline}
.news-src{font-size:11.5px;color:var(--muted)}
.empty-state{padding:22px;text-align:center;color:var(--muted);font-style:italic;background:rgba(250,246,239,.6);border:1px dashed var(--border);border-radius:8px;margin:12px 0}
footer{margin-top:56px;padding:32px 20px;background:var(--dark);color:#c9a84c;text-align:center}footer a{color:#f5f0e8}
@media(max-width:700px){table.events{font-size:13px}table.events td,table.events th{padding:8px}}
'''


def band_status_map():
    st = {}
    p = MEDIA / 'band_status.json'
    if p.exists():
        try:
            st = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            st = {}
    return st


def load_summaries_history():
    """{band: {month: text}} — primero DB (monthly_extracts), fallback a media/summaries_*.json."""
    out = defaultdict(dict)
    try:
        conn = sqlite3.connect(DB)
        rows = conn.execute(
            'SELECT band_name, month, summary FROM monthly_extracts '
            'WHERE summary IS NOT NULL AND summary != "" ORDER BY month').fetchall()
        conn.close()
        for band, month, text in rows:
            out[band][month] = clean_caption(text)
    except sqlite3.Error:
        pass
    if out:
        return out
    for p in sorted(MEDIA.glob('summaries_*.json')):
        m = p.stem.replace('summaries_', '')
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        for band, text in (data.get('summaries') or {}).items():
            if text:
                out[band][m] = clean_caption(text)
    return out


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    posts = conn.execute(
        '''SELECT band_name, shortcode, post_date, caption, post_url
           FROM posts WHERE band_name != 'Medio'
           ORDER BY post_date''').fetchall()
    concerts = conn.execute(
        '''SELECT date, band_name, event_name, event_type, city, venue, source_url
           FROM concerts WHERE band_name != 'Medio' AND date IS NOT NULL
           ORDER BY date''').fetchall()
    news = conn.execute(
        '''SELECT source, title, url, published FROM news_posts
           ORDER BY published DESC''').fetchall()
    conn.close()

    by_band_posts = defaultdict(list)
    for p in posts:
        by_band_posts[p['band_name']].append(p)
    by_band_concerts = defaultdict(list)
    for c in concerts:
        by_band_concerts[c['band_name']].append(c)

    # Noticias de prensa relevantes por banda (coincidencia en título).
    news_by_band = defaultdict(list)
    for n in news:
        t = (n['title'] or '').lower()
        for band in by_band_posts:
            if band.casefold() in t:
                news_by_band[band].append(n)

    status_map = band_status_map()
    summaries_hist = load_summaries_history()

    bands = sorted(set(by_band_posts) | set(PROFILES), key=lambda s: s.casefold())
    HISTORIAS.mkdir(parents=True, exist_ok=True)
    # Limpieza: eliminar fichas huérfanas (bandas que ya no existen o residuales).
    valid_slugs = {slug(b) for b in bands}
    for stale in HISTORIAS.glob('*.html'):
        if stale.name == 'index.html':
            continue
        if stale.stem not in valid_slugs:
            stale.unlink()
            print(f'  (limpieza) {stale.name}')
    generated = []

    for band in bands:
        posts_b = by_band_posts.get(band, [])
        concerts_b = by_band_concerts.get(band, [])
        news_b = news_by_band.get(band, [])
        prof = PROFILES.get(band, {})

        # Histórico mes a mes: posts + resumen editorial + conciertos + noticias por mes.
        months = defaultdict(lambda: {'posts': [], 'concerts': [], 'news': []})
        for p in posts_b:
            months[p['post_date'][:7]]['posts'].append(p)
        for c in concerts_b:
            months[(c['date'] or '')[:7]]['concerts'].append(c)
        for n in news_b:
            months[(n['published'] or '')[:7]]['news'].append(n)

        today = datetime.now().date()
        upcoming = [c for c in concerts_b if (c['date'] or '')[:10] >= today.isoformat()]
        past = [c for c in concerts_b if (c['date'] or '')[:10] < today.isoformat()]
        upcoming.sort(key=lambda c: c['date'])
        past.sort(key=lambda c: c['date'], reverse=True)

        st = status_map.get(band, {})
        status_badge = ''
        if st.get('status') == 'INACTIVA':
            status_badge = '<span class="badge badge-status">⚠️ inactiva</span>'
        elif st.get('status') == 'SOSPECHOSA':
            status_badge = '<span class="badge badge-status">🕰️ sin actividad</span>'

        parts = ['<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">',
                 '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
                 f'<title>{esc(band)} · Ficha histórica · Folk Metal Magazine</title>',
                 f'<style>{CSS}</style></head><body>']

        # Portada de la ficha
        img = best_photo_b64(band)
        parts.append(
            f'<header class="cover"><h1>{esc(band)}</h1>'
            f'<div class="sub">{esc(prof.get("genero") or "Folk Metal")}{status_badge}</div>'
            f'<div class="meta">{esc(prof.get("origen") or "")}'
            f'{" · " if prof.get("origen") else ""}formada en {esc(str(prof.get("formada") or "—"))}'
            f'</div>'
            f'<div class="stats">'
            f'<div><strong>{len(posts_b)}</strong> publicaciones</div>'
            f'<div><strong>{len(concerts_b)}</strong> conciertos</div>'
            f'<div><strong>{len(news_b)}</strong> noticias</div>'
            f'<div><strong>{len(months)}</strong> meses de actividad</div>'
            f'</div></header>')

        # Navegación
        parts.append('<nav class="section-nav">'
                     '<a href="#datos">📌 Datos</a><span>·</span>'
                     '<a href="#historia">📜 Historia mes a mes</a><span>·</span>'
                     '<a href="#conciertos">🎸 Conciertos</a><span>·</span>'
                     '<a href="#prensa">📰 Prensa</a><span>·</span>'
                     '<a href="#fuentes">📚 Fuentes</a><span>·</span>'
                     '<a href="../index.html">⬅ Portada</a><span>·</span>'
                     '<a href="../ediciones/">Revista mensual</a></nav>')
        parts.append('<main class="container">')

        # 1. Datos rápidos
        parts.append('<section id="datos"><div class="section-divider"><h2>📌 Datos de la banda</h2></div>')
        quick = []
        if prof.get('origen'):
            quick.append(('Origen', prof['origen']))
        if prof.get('formada'):
            quick.append(('Formada', str(prof['formada'])))
        if prof.get('sello'):
            quick.append(('Sello / Discográfica', prof['sello']))
        if prof.get('web'):
            quick.append(('Web', f'<a href="{esc(prof["web"])}" target="_blank" rel="noopener">{esc(prof["web"])}</a>'))
        if prof.get('instagram'):
            quick.append(('Instagram', prof['instagram']))
        if quick:
            parts.append('<div class="quick-grid">')
            for k, v in quick:
                parts.append(f'<div class="quick"><b>{esc(k)}</b><span>{v}</span></div>')
            parts.append('</div>')

        if prof.get('miembros'):
            parts.append('<div class="card"><h3>🎤 Componentes</h3><ul class="clean">')
            for m in prof['miembros']:
                parts.append(f'<li>{esc(m)}</li>')
            parts.append('</ul></div>')

        if prof.get('discografia'):
            parts.append('<div class="card"><h3>💿 Discografía</h3><ul class="clean">')
            for d in prof['discografia']:
                anio = d.get('anio') or 'próximo'
                nota = f' — {d["nota"]}' if d.get('nota') else ''
                parts.append(f'<li><b>{esc(d["titulo"])}</b> <span class="badge badge-past">{esc(str(anio))}</span>{esc(nota)}</li>')
            parts.append('</ul></div>')

        # 1a. Catálogo Spotify verificado (API oficial, con URLs) — si existe
        sp_disc = (prof.get('metricas') or {}).get('spotify_discografia') or []
        if sp_disc:
            parts.append('<div class="card"><h3>🎧 Catálogo en Spotify</h3><ul class="clean">')
            for a in sorted(sp_disc, key=lambda x: str(x.get('fecha') or ''), reverse=True):
                a_url = a.get('url') or '#'
                a_fecha = str(a.get('fecha') or '')[:10]
                a_tipo = a.get('tipo') or ''
                a_trk = a.get('total_tracks') or ''
                trk_html = f' <span class="post-date">{esc(str(a_trk))} temas</span>' if a_trk else ''
                parts.append(f'<li>{esc(a_fecha)} — <b>{esc(a["titulo"])}</b> '
                             f'<span class="badge badge-past">{esc(a_tipo)}</span>{trk_html} '
                             f'<a href="{esc(a_url)}" target="_blank" rel="noopener">🎧</a></li>')
            parts.append('</ul></div>')

        # 1b. Tracks del álbum principal (Spotify)
        sp_tracks = (prof.get('metricas') or {}).get('spotify_tracks_album_principal') or []
        if sp_tracks:
            parts.append('<div class="card"><h3>🎵 Tracks del álbum principal</h3><ul class="clean">')
            for t in sorted(sp_tracks, key=lambda x: x.get('numero') or 0):
                t_url = t.get('url') or '#'
                dur = t.get('duracion_ms') or 0
                mins = dur // 60000
                secs = (dur % 60000) // 1000
                parts.append(f'<li><span class="post-date">{t.get("numero", "")}.</span> '
                             f'<b>{esc(t["titulo"])}</b> <span style="color:var(--muted)">({mins}:{secs:02d})</span> '
                             f'<a href="{esc(t_url)}" target="_blank" rel="noopener">🎧</a></li>')
            parts.append('</ul></div>')

        # 1a. Críticas de discos en medios (prensa especializada)
        criticas = prof.get('criticas') or []
        if criticas:
            parts.append('<div class="card"><h3>📝 Críticas de discos</h3><ul class="clean">')
            for cr in sorted(criticas, key=lambda x: (str(x.get('disco') or ''), str(x.get('fecha') or ''))):
                cr_disco = cr.get('disco') or ''
                cr_medio = cr.get('medio') or ''
                cr_fecha = str(cr.get('fecha') or '')[:10]
                cr_url = cr.get('url') or '#'
                cr_extracto = cr.get('extracto') or ''
                parts.append(
                    f'<li><span class="badge badge-news">{esc(cr_medio)}</span> '
                    f'<b>{esc(cr_disco)}</b> <span class="post-date">({esc(cr_fecha)})</span><br>'
                    f'<span style="font-size:13px;color:#4b382b">"{esc(cr_extracto)}"</span><br>'
                    f'<a href="{esc(cr_url)}" target="_blank" rel="noopener" style="font-size:13px">{esc(cr.get("titulo") or cr_url)} 🔗</a></li>')
            parts.append('</ul></div>')

        if prof.get('estudios'):
            parts.append('<div class="card"><h3>🎚️ Estudios</h3><ul class="clean">')
            for e in prof['estudios']:
                parts.append(f'<li>{esc(e)}</li>')
            parts.append('</ul></div>')

        if prof.get('conexiones'):
            parts.append('<div class="card"><h3>🔗 Conexiones</h3><ul class="clean">')
            for c in prof['conexiones']:
                parts.append(f'<li>{esc(c)}</li>')
            parts.append('</ul></div>')

        if prof.get('hitos'):
            parts.append('<div class="card"><h3>🏰 Hitos clave</h3><ul class="clean">')
            for h in sorted(prof['hitos'], key=lambda x: str(x.get('fecha') or '')):
                parts.append(f'<li><b>{esc(str(h.get("fecha") or ""))}</b> — {esc(h.get("texto") or "")}</li>')
            parts.append('</ul></div>')

        if not quick and not prof.get('miembros') and not prof.get('discografia'):
            parts.append('<p class="empty-state">Ficha en construcción: datos pendientes de investigación.</p>')

        # 1b. Historia narrativa (web oficial / biografía curada)
        if prof.get('historia'):
            parts.append(f'<div class="card"><h3>🏛️ Historia</h3>'
                         f'<p style="font-size:15.5px;line-height:1.7;color:#33251c;margin:8px 0">{esc(prof["historia"])}</p></div>')

        # 1c. Sellos / discográficas (histórico)
        sellos = prof.get('sellos') or []
        if sellos:
            parts.append('<div class="card"><h3>🏷️ Sellos y discográficas</h3><ul class="clean">')
            for s in sellos:
                periodo = f'{s.get("desde", "?")}–{s.get("hasta") or "actualidad"}'
                nota = f' — {s["nota"]}' if s.get('nota') else ''
                parts.append(f'<li><b>{esc(s.get("sello", ""))}</b> <span class="badge badge-past">{esc(periodo)}</span>{esc(nota)}</li>')
            parts.append('</ul></div>')
        elif prof.get('sello'):
            parts.append(f'<div class="card"><h3>🏷️ Sello / Discográfica</h3>'
                         f'<p style="margin:6px 0">{esc(prof["sello"])}</p></div>')

        # 1d. Redes y enlaces
        redes = prof.get('redes') or {}
        if redes or prof.get('web') or prof.get('instagram'):
            parts.append('<div class="card"><h3>🌐 Redes y enlaces</h3><ul class="clean">')
            if prof.get('web') or redes.get('web'):
                u = redes.get('web') or prof['web']
                parts.append(f'<li>🌍 <a href="{esc(u)}" target="_blank" rel="noopener">Web oficial</a></li>')
            rmap = [('instagram', '📸 Instagram'), ('facebook', '📘 Facebook'),
                    ('youtube', '▶️ YouTube'), ('spotify', '🎧 Spotify'),
                    ('apple_music', '🍎 Apple Music'), ('tiktok', '🎵 TikTok')]
            for key, label in rmap:
                u = redes.get(key)
                if u:
                    parts.append(f'<li>{label}: <a href="{esc(u)}" target="_blank" rel="noopener">{esc(u.replace("https://", "").rstrip("/"))}</a></li>')
            if prof.get('instagram_seguidores'):
                parts.append(f'<li class="tl-tag" style="display:inline-block;margin-top:6px;background:#ead6a2;color:#725100">'
                             f'📈 {esc(prof["instagram_seguidores"])}</li>')
            parts.append('</ul></div>')

        # 1e. Métricas Spotify / YouTube / videoclips
        metricas = prof.get('metricas') or {}
        if metricas:
            parts.append('<div class="card"><h3>📊 Métricas</h3>')
            m_spotify = metricas.get('spotify_oyentes_mes')
            if m_spotify:
                parts.append(f'<div class="quick-grid" style="margin:10px 0">'
                             f'<div class="quick"><b>🎧 Spotify</b><span>{esc(m_spotify)} oyentes/mes</span></div>')
            m_follow = metricas.get('spotify_followers')
            if m_follow:
                parts.append(f'<div class="quick"><b>🎧 Seguidores</b><span>{esc(str(m_follow))}</span></div>')
            m_pop = metricas.get('spotify_popularity')
            if m_pop is not None:
                parts.append(f'<div class="quick"><b>🎧 Popularidad</b><span>{esc(str(m_pop))}/100</span></div>')
            m_yt = metricas.get('youtube_suscriptores')
            if m_yt:
                parts.append(f'<div class="quick"><b>▶️ YouTube</b><span>{esc(m_yt)} suscriptores</span></div>')
            if m_spotify or m_follow or m_pop or m_yt:
                parts.append('</div>')
            # Top tracks de Spotify (API oficial o scrape público)
            top_tracks = metricas.get('spotify_top_tracks') or []
            if top_tracks:
                parts.append('<h3 style="margin:14px 0 8px;font-size:15px">🎵 Canciones más escuchadas (Spotify)</h3>')
                for i, t in enumerate(top_tracks[:5], 1):
                    t_url = t.get('url') or '#'
                    t_pop = t.get('popularity')
                    t_pc = t.get('playcount')
                    if t_pc:
                        # Formato: 147.948
                        pc_str = f'{int(t_pc):,}'.replace(',', '.')
                        pc_html = f' <span class="badge badge-news">▶ {esc(pc_str)}</span>'
                    elif t_pop is not None:
                        pc_html = f' <span class="badge badge-news">pop {esc(str(t_pop))}</span>'
                    else:
                        pc_html = ''
                    parts.append(f'<div class="tl-post"><span class="post-date">#{i}</span>'
                                 f'<b>{esc(t.get("titulo", ""))}</b>{pc_html}'
                                 f' <span style="color:var(--muted)">{esc(t.get("album", ""))}</span>'
                                 f' <span style="color:var(--muted)">{esc(t.get("duracion", ""))}</span>'
                                 f' <a href="{esc(t_url)}" target="_blank" rel="noopener">🎧</a></div>')
            for v in (metricas.get('videoclips') or []):
                vurl = v.get('url') or '#'
                vvisitas = v.get('visitas') or '—'
                vnota = f' — {v["nota"]}' if v.get('nota') else ''
                parts.append(f'<div class="tl-post"><span class="post-date">🎬 {esc(v.get("fecha", ""))}</span>'
                             f'<b>{esc(v.get("titulo", ""))}</b> · {esc(vvisitas)} visitas · '
                             f'<a href="{esc(vurl)}" target="_blank" rel="noopener">ver en YouTube 🔗</a>{esc(vnota)}</div>')
            if metricas.get('spotify_oyentes_nota'):
                parts.append(f'<p style="font-size:12px;color:var(--muted);margin-top:8px">{esc(metricas["spotify_oyentes_nota"])}</p>')
            if metricas.get('youtube_nota'):
                parts.append(f'<p style="font-size:12px;color:var(--muted);margin:4px 0 0">{esc(metricas["youtube_nota"])}</p>')
            parts.append('</div>')

        # 1f. Equipo técnico (web oficial)
        if prof.get('equipo'):
            parts.append('<div class="card"><h3>🛠️ Equipo técnico</h3><ul class="clean">')
            for e in prof['equipo']:
                parts.append(f'<li>{esc(e)}</li>')
            parts.append('</ul></div>')

        # 1g. Prensa destacada (hitos en medios)
        prensa = prof.get('prensa') or []
        if prensa:
            parts.append('<div class="card"><h3>📰 Prensa destacada</h3><ul class="clean">')
            for pr in sorted(prensa, key=lambda x: str(x.get('fecha') or ''), reverse=True):
                pdate = str(pr.get('fecha') or '')[:10]
                parts.append(f'<li><span class="badge badge-news">{esc(pr.get("medio", ""))}</span> '
                             f'<b>{esc(pdate)}</b> — <a href="{esc(pr.get("url", "#"))}" target="_blank" rel="noopener">'
                             f'{esc(pr.get("titulo", ""))}</a></li>')
            parts.append('</ul></div>')

        parts.append('</section>')

        # 2. Historia mes a mes
        parts.append('<section id="historia"><div class="section-divider"><h2>📜 Historia mes a mes</h2></div>')
        if not months:
            parts.append('<p class="empty-state">Sin actividad registrada en el histórico (la DB acumula desde marzo 2026).</p>')
        else:
            parts.append('<div class="timeline">')
            for ym in sorted(months):
                mdata = months[ym]
                tags = []
                if mdata['posts']:
                    tags.append(f'{len(mdata["posts"])} publicaciones')
                if mdata['concerts']:
                    tags.append(f'{len(mdata["concerts"])} conciertos')
                if mdata['news']:
                    tags.append(f'{len(mdata["news"])} noticias')
                parts.append(f'<div class="tl-item"><div class="tl-month">{esc(month_label(ym))}</div>')
                parts.append('<div class="tl-body"><div class="tl-tags">' +
                             ''.join(f'<span class="tl-tag">{esc(t)}</span>' for t in tags) + '</div>')
                # Resumen editorial del mes (si existe)
                editorial = summaries_hist.get(band, {}).get(ym)
                if editorial:
                    parts.append(f'<p style="margin:6px 0 10px;font-size:14.5px;color:#33251c"><i>{esc(editorial)}</i></p>')
                # Conciertos del mes
                for c in sorted(mdata['concerts'], key=lambda c: c['date']):
                    icon = {'festival': '🎪', 'gira': '🗺️'}.get(c['event_type'] or '', '🎸')
                    label = ' — '.join(p for p in (c['event_name'], c['city'], c['venue']) if p) or 'Fecha anunciada'
                    link = c['source_url'] or '#'
                    parts.append(f'<div class="tl-post"><span class="post-date">{esc((c["date"] or "")[:10])}</span>'
                                 f'{icon} <b>{esc(c["band_name"] if c["band_name"] != band else "concierto")}</b> '
                                 f'{esc(label)} <a href="{esc(link)}" target="_blank" rel="noopener">🔗</a></div>')
                # Noticias de prensa del mes
                for n in mdata['news'][:3]:
                    parts.append(f'<div class="tl-post"><span class="post-date">{esc((n["published"] or "")[:10])}</span>'
                                 f'📰 <a href="{esc(n["url"])}" target="_blank" rel="noopener">{esc(clean_caption(n["title"]))}</a>'
                                 f' <span class="tl-tag" style="background:#f2c6a8;color:#7c2b0a">{esc(n["source"])}</span></div>')
                # Posts del mes (máx 5)
                for p in mdata['posts'][:5]:
                    cap = clean_caption(p['caption'])
                    if len(cap) > 180:
                        cap = cap[:177].rsplit(' ', 1)[0] + '…'
                    link = p['post_url'] or f'https://www.instagram.com/p/{p["shortcode"]}/'
                    parts.append(f'<div class="tl-post"><span class="post-date">{esc((p["post_date"] or "")[:10])}</span>'
                                 f'{esc(cap)} <a href="{esc(link)}" target="_blank" rel="noopener">🔗</a></div>')
                if len(mdata['posts']) > 5:
                    parts.append(f'<div class="tl-post" style="color:var(--muted);font-style:italic">'
                                 f'+ {len(mdata["posts"]) - 5} publicaciones más ese mes</div>')
                parts.append('</div></div>')
            parts.append('</div>')
        parts.append('</section>')

        # 3. Todos los conciertos (ordenados) — DB + conciertos históricos del perfil
        parts.append('<section id="conciertos"><div class="section-divider"><h2>🎸 Todos los conciertos</h2></div>')
        hist_concerts = []
        for hc in (prof.get('conciertos_historicos') or []):
            hc_date = str(hc.get('fecha') or '')
            if not hc_date:
                continue
            hist_concerts.append({
                'date': hc_date,
                'event_name': hc.get('evento') or hc.get('event_name'),
                'city': hc.get('ciudad') or hc.get('city'),
                'venue': hc.get('sala') or hc.get('venue'),
                'event_type': 'concierto',
                'source_url': hc.get('fuente') or hc.get('source_url'),
                '_compania': hc.get('compania') or '',
                '_hist': True,
            })
        db_dates = {(c['date'] or '')[:10] for c in concerts_b}
        merged = [dict(c) for c in concerts_b] + [hc for hc in hist_concerts if (hc['date'] or '')[:10] not in db_dates]
        if not merged:
            parts.append('<p class="empty-state">Sin conciertos registrados en el histórico.</p>')
        else:
            parts.append('<table class="events"><thead><tr><th>Fecha</th><th>Evento</th><th>Tipo</th><th>Ubicación</th><th>Estado</th></tr></thead><tbody>')
            all_c = sorted(merged, key=lambda c: c['date'])
            for c in all_c:
                is_future = (c['date'] or '')[:10] >= today.isoformat()
                icon = {'festival': '🎪', 'gira': '🗺️'}.get(c['event_type'] or '', '🎸')
                label_parts = [c.get('event_name') or '']
                if c.get('_compania'):
                    label_parts.append(f'con {c["_compania"]}')
                label = ' — '.join(p for p in label_parts if p) or '—'
                loc = ' — '.join(p for p in (c.get('city'), c.get('venue')) if p) or '—'
                link = c.get('source_url') or '#'
                kind = c.get('event_type') or 'concierto'
                state = '<span class="badge badge-future">próximo</span>' if is_future else '<span class="badge badge-past">pasado</span>'
                row_cls = 'future' if is_future else 'past'
                parts.append(f'<tr class="{row_cls}"><td>{esc((c["date"] or "")[:10])}</td>'
                             f'<td>{icon} {esc(label)} <a href="{esc(link)}" target="_blank" rel="noopener">🔗</a></td>'
                             f'<td>{esc(kind)}</td><td>{esc(loc)}</td><td>{state}</td></tr>')
            parts.append('</tbody></table>')
        parts.append('</section>')

        # 4. Prensa (medios monitorizados + prensa destacada del perfil)
        parts.append('<section id="prensa"><div class="section-divider"><h2>📰 Prensa y medios</h2></div>')
        prof_prensa = prof.get('prensa') or []
        if not news_b and not prof_prensa:
            parts.append('<p class="empty-state">Sin menciones en los medios monitorizados (Hellpress, Metalcry, RafaBasa, The Dark Melody).</p>')
        else:
            for pr in sorted(prof_prensa, key=lambda x: str(x.get('fecha') or ''), reverse=True):
                parts.append(f'<div class="news-card"><span class="news-src">{esc(pr.get("medio", ""))} · {esc(str(pr.get("fecha") or "")[:10])}</span><br>'
                             f'<a href="{esc(pr.get("url", "#"))}" target="_blank" rel="noopener">{esc(pr.get("titulo", ""))}</a></div>')
            for n in news_b[:10]:
                parts.append(f'<div class="news-card"><span class="news-src">{esc(n["source"])} · {esc((n["published"] or "")[:10])}</span><br>'
                             f'<a href="{esc(n["url"])}" target="_blank" rel="noopener">{esc(clean_caption(n["title"]))}</a></div>')
        parts.append('</section>')

        # 5. Fuentes de verificación (contrastar los datos)
        parts.append('<section id="fuentes"><div class="section-divider"><h2>📚 Fuentes</h2></div>')
        fuentes = []
        seen = set()
        def add_fuente(label, url):
            if url and url not in seen and url != '#':
                seen.add(url)
                fuentes.append((label, url))
        # Fuentes del brief (Metal Archives, Wikipedia)
        for f in (prof.get('fuentes') or []):
            if ':' in str(f):
                label, _, url = str(f).partition(': ')
                add_fuente(label.strip().capitalize(), url.strip())
        # Prensa destacada
        for pr in (prof.get('prensa') or []):
            add_fuente(f'Prensa · {pr.get("medio", "")}', pr.get('url'))
        # Críticas de discos
        for cr in (prof.get('criticas') or []):
            add_fuente(f'Crítica · {cr.get("medio", "")} ({cr.get("disco", "")})', cr.get('url'))
        # Conciertos históricos
        for hc in (prof.get('conciertos_historicos') or []):
            add_fuente(f'Concierto · {hc.get("evento", hc.get("fecha", ""))}', hc.get('fuente') or hc.get('source_url'))
        # Videoclips
        for v in ((prof.get('metricas') or {}).get('videoclips') or []):
            add_fuente(f'Videoclip · {v.get("titulo", "")}', v.get('url'))
        # Web y redes
        redes = prof.get('redes') or {}
        add_fuente('Web oficial', redes.get('web') or prof.get('web'))
        add_fuente('Spotify', redes.get('spotify'))
        add_fuente('YouTube', redes.get('youtube'))
        add_fuente('Instagram', redes.get('instagram'))
        add_fuente('Facebook', redes.get('facebook'))
        add_fuente('TikTok', redes.get('tiktok'))
        # Fuentes de la DB (posts y conciertos)
        for c in [dict(x) for x in concerts_b][:6]:
            add_fuente(f'Concierto · {c.get("event_name") or c.get("date", "")}', c.get('source_url'))
        if fuentes:
            parts.append('<div class="card"><p style="font-size:13.5px;color:var(--muted);margin:0 0 10px">'
                         'Enlaces para contrastar los datos de esta ficha. Cada dato curado apunta a su fuente original.</p><ul class="clean">')
            for label, url in sorted(fuentes, key=lambda x: x[0].casefold()):
                parts.append(f'<li>🔗 <b>{esc(label)}</b> — <a href="{esc(url)}" target="_blank" rel="noopener">{esc(url)}</a></li>')
            parts.append('</ul></div>')
        else:
            parts.append('<p class="empty-state">Sin fuentes externas registradas; los datos provienen del archivo curado del proyecto.</p>')
        parts.append('</section>')

        parts.append(f'</main><footer><a href="../index.html">⬅ Índice de fichas</a> · '
                     f'<a href="../ediciones/">Revista mensual</a> · '
                     f'<a href="#fuentes">📚 Fuentes</a><br><br>'
                     f'Ficha histórica de {esc(band)} · Folk Metal Magazine · '
                     f'datos verificables desde publicaciones, prensa y archivo curado</footer>')
        parts.append('</body></html>')

        out = HISTORIAS / f'{slug(band)}.html'
        out.write_text(''.join(parts), encoding='utf-8')
        generated.append((band, out, len(posts_b), len(concerts_b), len(news_b), len(months)))
        print(f'  {out.name}: posts={len(posts_b)} conciertos={len(concerts_b)} '
              f'noticias={len(news_b)} meses={len(months)}')

    # Índice de fichas
    index_css = CSS
    idx = ['<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
           '<title>Fichas históricas · Folk Metal Magazine</title>',
           f'<style>{index_css}'
           '.band-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px;margin:20px 0}'
           '.band-tile{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;text-align:center;box-shadow:0 5px 15px rgba(61,43,31,.08);transition:transform .2s,box-shadow .2s;text-decoration:none;color:var(--text);display:block}'
           '.band-tile:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(61,43,31,.15)}'
           '.band-tile img{width:110px;height:110px;object-fit:cover;border-radius:50%;border:4px solid var(--cream);outline:1px solid var(--border);margin-bottom:10px}'
           '.band-tile h3{margin:6px 0 2px;color:var(--accent);font-size:17px}'
           '.band-tile p{margin:0;font-size:12.5px;color:var(--muted)}'
           '.band-tile .mini{font-size:11.5px;color:var(--gold);margin-top:6px}'
           '</style></head><body>']
    idx.append('<header class="cover"><h1>FICHAS<br>HISTÓRICAS</h1>'
               '<div class="sub">La profundidad de la escena folk metal española</div>'
               '<div class="meta">Histórico mes a mes · conciertos completos · prensa · discografía · componentes</div>'
               '<div class="stats"><div><strong>29</strong> bandas</div>'
               '<div><strong>∞</strong> profundidad</div></div></header>')
    idx.append('<nav class="section-nav"><a href="../index.html">⬅ Revista</a><span>·</span>'
               '<a href="../ediciones/">Ediciones</a></nav>')
    idx.append('<main class="container"><div class="section-divider"><h2>🗂️ Índice de bandas</h2></div>')
    idx.append('<p class="lead" style="color:var(--muted);text-align:center;max-width:760px;margin:0 auto 22px">'
               'Cada ficha acumula el histórico completo de la banda: actividad mes a mes, todos los conciertos '
               'registrados, menciones de prensa, discografía y datos curados. La revista mensual es el índice '
               'accesible; aquí está la profundidad.</p>')
    idx.append('<div class="band-grid">')
    for band, path, np_, nc, nn, nm in sorted(generated, key=lambda g: g[0].casefold()):
        prof = PROFILES.get(band, {})
        loc = prof.get('origen') or ''
        idx.append(f'<a class="band-tile" href="{path.name}">'
                   f'<img src="{best_photo_b64(band)}" alt="Foto {esc(band)}">'
                   f'<h3>{esc(band)}</h3>'
                   f'<p>{esc(loc)}</p>'
                   f'<div class="mini">{np_} posts · {nc} conciertos · {nm} meses</div></a>')
    idx.append('</div>')
    idx.append(f'</main><footer>Folk Metal Magazine · Fichas históricas · {len(generated)} bandas</footer>')
    idx.append('</body></html>')
    (HISTORIAS / 'index.html').write_text(''.join(idx), encoding='utf-8')
    print(f'Generated historias/index.html | {len(generated)} fichas → {HISTORIAS}')

    update_home_index(generated)


def update_home_index(generated):
    """Inserta el índice de bandas (grid con logos y detalle) en la portada
    (index.html raíz). Se regenera en cada publish para que la portada muestre
    el mismo grid que historias/index.html, enlazando a las fichas."""
    if not INDEX.exists():
        return
    html = INDEX.read_text(encoding='utf-8')
    marker_start = '<!-- BAND-INDEX:START -->'
    marker_end = '<!-- BAND-INDEX:END -->'
    tiles = []
    for band, path, np_, nc, nn, nm in sorted(generated, key=lambda g: g[0].casefold()):
        prof = PROFILES.get(band, {})
        loc = prof.get('origen') or ''
        tiles.append(f'<a class="band-tile" href="historias/{path.name}">'
                     f'<img src="{logo_b64(band)}" alt="Logo {esc(band)}">'
                     f'<h3>{esc(band)}</h3>'
                     f'<p>{esc(loc)}</p>'
                     f'<div class="mini">{np_} posts · {nc} conciertos · {nm} meses</div></a>')
    css = ('<style>'
           '.band-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));'
           'gap:14px;margin:20px 0}'
           '.band-tile{background:var(--card);border:1px solid var(--card-border);'
           'border-radius:10px;padding:16px;text-align:center;box-shadow:0 5px 15px rgba(61,43,31,.08);'
           'transition:transform .2s,box-shadow .2s;text-decoration:none;color:var(--text);display:block}'
           '.band-tile:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(61,43,31,.15)}'
           '.band-tile img{width:100px;height:100px;object-fit:cover;border-radius:50%;border:4px solid var(--cream);'
           'outline:1px solid var(--border);margin-bottom:10px}'
           '.band-tile h3{margin:6px 0 2px;color:var(--accent);font-size:16px}'
           '.band-tile p{margin:0;font-size:12.5px;color:var(--muted)}'
           '.band-tile .mini{font-size:11.5px;color:var(--gold);margin-top:6px}'
           '</style>')
    block = (css +
             '<div class="section-divider"><h2>⚔️ Bandas con ficha</h2></div>\n'
             '<p style="color:var(--muted);text-align:center;max-width:760px;margin:0 auto 22px">'
             'Cada banda tiene una ficha histórica completa: actividad mes a mes, conciertos, '
             'prensa, discografía y datos curados.</p>\n'
             '<div class="band-grid">' + ''.join(tiles) + '</div>\n'
             '<p style="text-align:center;margin:18px 0 6px"><a href="historias/index.html" '
             'style="color:var(--accent)">🗂️ Índice completo de fichas →</a></p>')
    if marker_start in html and marker_end in html:
        # Reemplazar el bloque anterior (sin duplicar).
        pattern = re.compile(re.escape(marker_start) + r'.*?' + re.escape(marker_end), re.S)
        html = pattern.sub(f'{marker_start}\n{block}\n{marker_end}', html)
    else:
        # Insertar antes del footer.
        anchor = '</footer>'
        html = html.replace(anchor,
                            f'{marker_start}\n{block}\n{marker_end}\n{anchor}', 1)
    INDEX.write_text(html, encoding='utf-8')
    print(f'  portada index.html actualizada con índice de {len(tiles)} bandas')


if __name__ == '__main__':
    main()
