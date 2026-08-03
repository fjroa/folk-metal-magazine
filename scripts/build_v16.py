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
next_month_date = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1)
agenda_end_date = (next_month_date.replace(day=28) + timedelta(days=124)).replace(day=1)

CSS = '''
:root{scroll-behavior:smooth;--cream:#f5f0e8;--paper:#ede4d3;--dark:#2c1810;--text:#3d2b1f;--accent:#8b2500;--gold:#b8860b;--muted:#8c7b6b;--card:#faf6ef;--border:#d4c5a9;--highlight:#fff8e7}
*{box-sizing:border-box}body{margin:0;background:#e8dcc8;background-image:url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.08'/%3E%3C/svg%3E"),linear-gradient(180deg,#ede4d3,#d9ccb5);color:var(--text);font:15px/1.55 Georgia,'Times New Roman',serif}.cover{background:linear-gradient(160deg,#2c1810,#4a2820,#3d1f15,#2c1810);color:var(--gold);text-align:center;padding:80px 20px 60px;position:relative}.cover h1{font-size:clamp(38px,8vw,72px);letter-spacing:5px;margin:0}.cover .sub{color:#c9a84c;font-size:clamp(15px,3vw,22px);font-style:italic;margin:12px}.cover .meta{color:#a09080;font-size:13px;line-height:2}.cover .stats{display:flex;justify-content:center;gap:28px;flex-wrap:wrap;margin:28px 0 0}.cover strong{display:block;font-size:28px;color:var(--gold)}.container{max-width:1000px;margin:0 auto;padding:0 24px}@media(max-width:700px){.container{padding:0 12px}}.section-nav{display:flex;justify-content:center;gap:14px;flex-wrap:wrap;padding:20px 12px 8px;font-size:13px}.section-nav a{color:var(--accent);text-decoration:none}.section-nav a:hover{color:var(--gold)}.section-divider{text-align:center;padding:46px 0 20px}.section-divider h2{font-size:clamp(25px,4vw,40px);color:var(--accent);letter-spacing:2px;border-top:2px solid var(--border);border-bottom:2px solid var(--border);padding:20px;margin:0}.toc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:7px}.toc-card,.band-card,.hl-card,.news-card{background:var(--card);border:1px solid var(--border);border-radius:4px}.toc-card{padding:9px;text-align:center}.toc-card img{width:32px;height:32px;display:block;margin:0 auto 4px}.toc-card a{color:var(--accent);text-decoration:none;font-size:13px}.toc-num{font-size:10px;color:var(--muted);display:block}.lead{color:var(--muted);font-size:13px;text-align:center;margin:0 auto 18px;max-width:760px}.hl-list{display:grid;gap:9px}.hl-card{display:flex;overflow:hidden}.hl-card img{width:100px;height:92px;object-fit:cover;flex:0 0 auto;background:var(--dark)}.hl-body{padding:10px 14px}.hl-band{color:var(--accent);font-size:14px}.hl-text{font-size:13px;margin-top:4px}.calendar{max-width:960px;margin:auto}.cal-head,.cal-row{display:grid;grid-template-columns:repeat(7,1fr)}.cal-head div{padding:8px;text-align:center;color:var(--gold);font-size:12px;border-bottom:1px solid var(--border)}.cal-cell{min-height:112px;padding:6px;border-right:1px solid var(--border);border-bottom:1px solid var(--border);background:rgba(250,246,239,.55)}.cal-cell:nth-child(7n){border-right:0}.cal-empty{background:rgba(237,228,211,.4)}.cal-day{font-size:12px;color:var(--accent);font-weight:bold}.cal-event{font-size:10px;line-height:1.25;margin-top:5px}.cal-event a{color:var(--accent);text-decoration:none}.band-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}.band-card-wrapper{position:relative}.top-link{position:absolute;right:9px;top:7px;color:var(--accent);font-size:11px;text-decoration:none;opacity:.5}.band-card{overflow:hidden}.band-header{display:flex;gap:12px;padding:12px;border-bottom:1px solid #f0ebe0;align-items:center}.band-header img{width:74px;height:74px;border-radius:4px}.band-header .name{font-size:17px;color:var(--accent)}.metrics{font-size:11px;color:var(--muted);margin-top:3px}.count{font-size:10px;color:var(--muted)}.band-summary{padding:10px 12px;font-size:12.5px;font-style:italic;border-bottom:1px solid #f0ebe0}.post-item{padding:8px 12px;border-bottom:1px solid #eee5d7;font-size:12px}.post-date{color:var(--gold);font-size:10px;margin-right:8px}.post-link{float:right}.post-link a{color:var(--accent);text-decoration:none;font-size:14px}.collapsed{display:none}.more-row{cursor:pointer;text-align:center;color:var(--accent);font-size:11px;font-style:italic;padding:8px}.more-row:hover{background:var(--highlight)}.news-list{display:grid;gap:7px;max-width:900px;margin:auto}.news-card{padding:9px 12px;font-size:12px}.news-card a{color:var(--accent);text-decoration:none}.news-source{color:var(--muted);font-size:10px}.metrics-table{width:100%;border-collapse:collapse;font-size:12px}.metrics-table th,.metrics-table td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--border)}.metrics-table th{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px}.metrics-table tr:hover td{background:var(--highlight)}.up{color:#287a3e}.down{color:#a52c1c}.flat{color:var(--muted)}footer{text-align:center;padding:45px 20px;color:var(--muted);font-size:11px}footer a{color:var(--accent);text-decoration:none}
'''

MODERN_CSS = '''
.cover{isolation:isolate;overflow:hidden;padding:clamp(64px,10vw,112px) 20px 72px;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180' viewBox='0 0 180 180'%3E%3Cg fill='none' stroke='%23b8860b' stroke-opacity='.13'%3E%3Cpath d='M0 30h180M0 90h180M0 150h180M30 0v180M90 0v180M150 0v180'/%3E%3C/g%3E%3C/svg%3E"),linear-gradient(135deg,#24100c 0%,#563126 50%,#24100c 100%)}
.cover:after{content:'✦';position:absolute;inset:18px;border:1px solid rgba(184,134,11,.35);color:rgba(201,168,76,.5);font-size:18px;text-align:left;padding:10px;pointer-events:none}.cover h1{position:relative;font-weight:normal;line-height:.93;text-shadow:0 4px 18px #160805}.cover .sub{letter-spacing:2px}.cover .stats>div{min-width:128px;padding:13px 20px;border:1px solid rgba(184,134,11,.45);border-radius:50px;background:rgba(20,8,5,.35);box-shadow:0 5px 16px rgba(0,0,0,.2)}
.section-nav{position:sticky;top:0;z-index:5;background:rgba(245,240,232,.94);border-bottom:1px solid var(--border);box-shadow:0 3px 14px rgba(61,43,31,.08);letter-spacing:.4px}.section-nav a{transition:color .2s,transform .2s}.section-nav a:hover{transform:translateY(-1px)}
.section-divider{padding:58px 0 22px}.section-divider h2{position:relative;border:0;padding:0 0 16px;letter-spacing:3px;text-transform:uppercase}.section-divider h2:after{content:'';display:block;width:100%;height:3px;margin-top:16px;background:linear-gradient(90deg,transparent,var(--gold),transparent);opacity:.7}
.toc-grid{gap:10px}.toc-card,.band-card,.hl-card,.news-card{box-shadow:0 5px 15px rgba(61,43,31,.08);transition:transform .2s,box-shadow .2s}.toc-card:hover,.band-card:hover,.hl-card:hover,.news-card:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(61,43,31,.15)}.toc-card{padding:12px;border-radius:7px;position:relative}.toc-card a{display:block}.toc-card img{border-radius:50%;object-fit:cover}.toc-hist{position:absolute;top:6px;right:8px;font-size:13px;text-decoration:none;opacity:.75}.toc-hist:hover{opacity:1}.lead{max-width:760px;margin:0 auto 24px;text-align:center;font-size:16px;line-height:1.7}.empty-state{padding:28px;text-align:center;color:var(--muted);font-style:italic;background:rgba(250,246,239,.6);border:1px dashed var(--border)}
.hl-feature{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,1fr);margin:0 0 18px;background:var(--card);border-left:5px solid var(--gold);border-radius:8px;overflow:hidden;box-shadow:0 8px 22px rgba(61,43,31,.13);transition:transform .2s,box-shadow .2s}.hl-feature:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(61,43,31,.18)}.hl-feature img{width:100%;height:100%;min-height:270px;object-fit:cover}.hl-feature-body{padding:28px 30px;display:flex;flex-direction:column;justify-content:center}.hl-band{font-family:Georgia,serif;color:var(--accent);font-size:18px;font-weight:bold;letter-spacing:.5px}.hl-feature p{font-size:19px;line-height:1.55;margin:14px 0 22px}.source-link{color:var(--accent);font-size:13px;font-weight:bold;text-decoration:none}.source-link:hover{text-decoration:underline}.hl-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.hl-card{display:grid;grid-template-columns:120px 1fr;overflow:hidden;border-left:4px solid var(--gold);border-radius:7px}.hl-card img{width:120px;height:100%;min-height:150px;object-fit:cover}.hl-body{padding:16px}.hl-text{margin-top:8px;line-height:1.55}.hl-text .source-link{display:block;margin-top:10px}
.agenda-month{margin:8px 0 12px;text-align:center;color:var(--accent);font-size:22px;letter-spacing:1px}.calendar{border:1px solid var(--border);border-radius:8px;overflow:hidden;box-shadow:0 6px 18px rgba(61,43,31,.08)}.cal-head{background:var(--dark);color:#f5f0e8;font-weight:bold;letter-spacing:1px}.cal-cell{min-height:112px;background:rgba(250,246,239,.72);border-color:var(--border)}.cal-cell:nth-child(odd){background:rgba(237,228,211,.5)}.cal-day{color:var(--accent);font-size:15px;font-weight:bold}.cal-event{margin:5px 2px;padding:6px;border-radius:5px;border-left:3px solid var(--gold);background:#fff8e7;line-height:1.3;font-size:12px}.cal-event strong{display:block;margin-top:3px}.cal-event a{color:var(--text);text-decoration:none}.event-badge{display:inline-block;padding:2px 6px;border-radius:20px;font-size:10px;text-transform:uppercase;letter-spacing:.4px;font-weight:bold}.event-festival .event-badge{background:#f2c6a8;color:#7c2b0a}.event-concierto .event-badge{background:#ead6a2;color:#725100}.event-gira .event-badge{background:#c6d8c2;color:#31553a}.agenda-later{margin-top:24px;padding:0 4px 4px;border-top:2px solid var(--gold)}.agenda-later h3{margin:0 -4px 8px;padding:10px 12px;background:linear-gradient(90deg,rgba(184,134,11,.2),transparent);color:var(--accent);letter-spacing:1px}.agenda-line{display:flex;align-items:center;gap:8px;padding:9px 4px;border-bottom:1px solid rgba(212,197,169,.65);transition:background .2s}.agenda-line:hover{background:rgba(255,248,231,.7)}.agenda-line>a{margin-left:auto;text-decoration:none}.agenda-detail{color:var(--muted)}
.band-grid{gap:20px}.band-card-wrapper .top-link{opacity:.5;transition:opacity .2s}.band-card-wrapper:hover .top-link{opacity:1}.band-card{border-radius:8px}.band-header img{border-radius:8px;object-fit:cover}.post-item{border-bottom-color:rgba(212,197,169,.65);transition:background .2s;padding:10px 6px}.post-item:hover{background:rgba(255,248,231,.65)}.news-list{gap:10px}.news-card{border-left:4px solid var(--accent);border-radius:6px;transition:transform .2s,box-shadow .2s}.news-card a{color:var(--accent);font-size:16px}.metrics-table{box-shadow:0 6px 18px rgba(61,43,31,.08);overflow:hidden;border-radius:7px}.metrics-table tr{transition:background .2s}.metrics-table tbody tr:hover{background:#fff8e7}.metrics-table th{letter-spacing:1px}
footer{margin-top:64px;padding:36px 20px;background:var(--dark);color:#c9a84c}footer a{color:#f5f0e8}@media(max-width:700px){.hl-feature{display:block}.hl-feature img{height:210px;min-height:0}.hl-feature-body{padding:20px}.hl-feature p{font-size:17px}.hl-list{grid-template-columns:1fr}.hl-card{grid-template-columns:105px 1fr}.hl-card img{width:105px;min-height:135px}.cal-cell{min-height:90px}.cal-event{font-size:11px;padding:4px 2px}.cal-event a{display:block}.agenda-line{align-items:flex-start;flex-wrap:wrap}.agenda-detail{display:block}.agenda-line>a{margin-left:0}}
'''

# Overrides kept separate so the base parchment language remains easy to audit.
EDITORIAL_CSS = '''
body{font-variant-numeric:oldstyle-nums} .cover h1{text-shadow:0 4px 18px #160805}
 .gordo-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:12px}.gordo-grid .hl-card:first-child{border-top-width:7px}.hl-card{display:flex;flex-direction:column;background:rgba(250,246,239,.94);box-shadow:0 8px 20px rgba(61,43,31,.12)}.hl-card img{width:100%;object-fit:cover}.ph-xl{height:300px}.ph-lg{height:240px}.ph-md{height:190px}.hl-card:hover{transform:translateY(-2px)}.hl-card .hl-band{font-size:17px}.hl-card .hl-text{font-size:15px;line-height:1.55}.hl-card .source-link{display:none}.hl-body{padding:16px}
 .tile-a,.tile-b,.tile-c,.tile-d{transition:transform .2s,border-radius .2s}.tile-a{border-radius:24px 6px 24px 6px;transform:rotate(-1deg)}.tile-b{border-radius:6px 24px 6px 24px;transform:rotate(1deg)}.tile-c{border-radius:50% 8px 50% 8px / 30% 8px 30% 8px;transform:rotate(-1deg)}.tile-d{border-radius:12px 40px 12px 40px;transform:rotate(1deg)}.tile-a:hover,.tile-b:hover,.tile-c:hover,.tile-d:hover{transform:rotate(0)}.band-lead{font-size:18px;font-weight:600;color:var(--accent);line-height:1.45}.band-body{font-size:14px;line-height:1.6;margin-top:5px}.status-badge{font:700 10px ui-sans-serif,system-ui,sans-serif;padding:2px 7px;border-radius:20px;vertical-align:middle;margin-left:6px;letter-spacing:.3px}.status-bad{background:#f3d9d9;color:#8b2500;border:1px solid #c99}.status-warn{background:#f6e9c8;color:#7a5c00;border:1px solid #d8b84f}
.band-card-wrapper{position:relative}.more-row{cursor:pointer;margin-top:10px;padding:9px;text-align:center;border:1px solid var(--border);border-radius:4px;color:var(--accent);font:700 12px ui-sans-serif,system-ui,sans-serif;background:var(--highlight)}
.metrics-table{font-variant-numeric:tabular-nums}.metrics-table tbody tr:nth-child(even){background:rgba(237,228,211,.42)}.metrics-table tbody tr:hover{background:var(--highlight)}.metrics-table th{position:sticky;top:49px;z-index:1}.listeners{min-width:180px}.bar-track{height:7px;margin-top:5px;background:#dfd2bd;border-radius:9px;overflow:hidden}.bar{height:100%;background:linear-gradient(90deg,#8b5a13,var(--gold),#d8b84f);border-radius:9px}.medal{font-size:18px;margin-right:5px}
.band-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:26px}.band-card-wrapper.wide{grid-column:span 2}.band-card{border-radius:2px;border-top:4px solid var(--accent);background:rgba(250,246,239,.94)}.band-header{gap:18px;padding:18px}.band-header img{width:140px;height:140px;border:5px solid var(--cream);outline:1px solid var(--border);box-shadow:0 4px 12px rgba(61,43,31,.18)}.band-header .name,.band-name{font-size:20px;font-weight:bold;line-height:1.2;color:#2f2118}.band-header .metrics,.band-header .count{font-size:12px;color:#4b382b}
.hist-link{margin-top:4px}.hist-link a{font-size:12.5px;color:var(--accent);text-decoration:none;border-bottom:1px dotted var(--gold)}.hist-link a:hover{color:var(--gold)}.band-summary{font-size:15px;line-height:1.6;color:#33251c;padding:0 18px 16px}.post-item{font-size:13.5px;line-height:1.55;color:#3b2a20}.post-date{font-size:11px;color:#594637;font-weight:bold}.more-row{font-size:12px}.band-card-wrapper.reverse .band-header{flex-direction:row-reverse;text-align:right}.band-card-wrapper.reverse .band-header>div{flex:1}.agenda-month{font-size:23px}.cal-cell{min-height:126px;padding:8px}.cal-event{font-size:11px;padding:7px 6px;line-height:1.4}.cal-day{font-size:16px}.event-badge{font-size:10px}.metrics-table th{font-size:13px}.metrics-table td{font-size:14px;padding:12px 10px}.metrics-table .band-name{font-size:15px}.metrics-table .listeners strong{font-size:14px}
 @media(max-width:700px){.gordo-grid{grid-template-columns:1fr 1fr;gap:12px}.hl-card img{height:180px}.band-grid{grid-template-columns:1fr}.band-card-wrapper.wide{grid-column:auto}.band-header img{width:110px;height:110px}.band-card-wrapper.reverse .band-header{flex-direction:row;text-align:left}.cal-cell{min-height:96px;padding:5px 3px}.cal-event{font-size:11px;padding:5px 2px}.metrics-table th,.metrics-table td{padding:9px 6px}.listeners{min-width:115px}}
'''

# v16.3 — Fix Lo Gordo (banda+texto SIEMPRE visibles) + layout ancho 90% + tipografía mayor.
# La causa del bug: la imagen heredaba height:100%+flex:0 0 auto de MODERN_CSS y el grid
# estiraba las tarjetas de la fila → la foto ocupaba todo el alto y empujaba .hl-body fuera
# (recortado por overflow:hidden). Fix: altura FIJA en la imagen (flex:none) y body con flex:1.
WIDE_CSS = '''
body{font-size:16.5px;line-height:1.62}
.container{width:90%;max-width:1700px;margin:0 auto;padding:0 24px}
.cover h1{font-size:clamp(44px,9vw,88px)}
.section-divider h2{font-size:clamp(28px,5vw,48px)}
.lead{font-size:17px}
.toc-grid{grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}.toc-card{padding:12px}.toc-card img{width:44px;height:44px}.toc-card a{font-size:14.5px}.toc-num{font-size:11px}
.gordo-grid{align-items:start}
.hl-card{display:flex;flex-direction:column;overflow:hidden;background:rgba(250,246,239,.96);box-shadow:0 8px 20px rgba(61,43,31,.12);border:1px solid var(--border);border-radius:10px}
.hl-card img{display:block;width:100%;height:auto;flex:none;object-fit:cover}
.hl-card img.ph-xl{height:300px}.hl-card img.ph-lg{height:240px}.hl-card img.ph-md{height:190px}
.hl-card .hl-body{display:flex;flex-direction:column;flex:1;padding:16px 18px 20px}
.hl-card .hl-band{font-size:20px;font-weight:bold;color:var(--accent);margin-bottom:6px}
.hl-card .hl-text{font-size:16.5px;line-height:1.6;color:var(--text)}
.band-card-wrapper .band-header .name{font-size:23px}
.band-summary{font-size:16.5px;line-height:1.65}
.post-item{font-size:15px;line-height:1.6}
.metrics-table td{font-size:15px;padding:13px 11px}.metrics-table th{font-size:14px}
.cal-event{font-size:12.5px}.cal-day{font-size:17px}
@media(max-width:700px){.container{width:94%;padding:0 12px}.hl-card img.ph-xl,.hl-card img.ph-lg,.hl-card img.ph-md{height:170px}.hl-card .hl-band{font-size:17px}.hl-card .hl-text{font-size:15px}}
'''


def esc(x):
    return html.escape(str(x or ''), quote=True)


def clean_caption(text):
    text = text or ''
    replacements = [
        (r'&\s*#039\s*;', "'"), (r'&\s*#8217\s*;', "'"),
        (r'&\s*#39\s*;', "'"), (r'&\s*amp\s*;', '&'),
        (r'&\s*quot\s*;', '"'), (r'&\s*nbsp\s*;', ''),
    ]
    for _ in range(2):
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


def hslug(name):
    # Slug para archivos de ficha histórica (ASCII, coincide con build_band_historias).
    s = name.lower().strip()
    dia = {'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u', 'ÿ': 'y', 'è': 'e',
           'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
    out = ''.join(str(dia.get(ch, ch)) for ch in s)
    return re.sub(r'[^a-z0-9]+', '-', out).strip('-')


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


# Clasificación de fotos (FOTO de la banda vs CARTEL) generada por folk_photo_choice.py
_photo_choices_path = MEDIA / f'photo_choices_{MONTH}.json'
photo_choices = {}
if _photo_choices_path.exists():
    try:
        photo_choices = json.loads(_photo_choices_path.read_text(encoding='utf-8'))
    except Exception:
        photo_choices = {}

def _rank_for(band, path):
    """Score de una foto según la clasificación: FOTO=1, DESCONOCIDO=0.5, CARTEL=0, sin dato=0.5."""
    sc = path.stem.rsplit('_', 1)[1] if '_' in path.stem else ''
    for item in photo_choices.get(band, []):
        if item.get('shortcode') == sc or (item.get('shortcode') is None and item.get('file') == path.name):
            return item.get('score', 0.5)
    return 0.5

# Estado de actividad (band_status.py): ACTIVA / SOSPECHOSA / INACTIVA
_band_status_path = MEDIA / 'band_status.json'
band_status = {}
if _band_status_path.exists():
    try:
        band_status = json.loads(_band_status_path.read_text(encoding='utf-8'))
    except Exception:
        band_status = {}

def status_badge(band):
    st = band_status.get(band, {}).get('status')
    if st == 'INACTIVA':
        note = band_status.get(band, {}).get('note', '')
        return f' <span class="status-badge status-bad" title="Inactiva: {esc(note)}">⚠️ inactiva</span>'
    if st == 'SOSPECHOSA':
        return ' <span class="status-badge status-warn" title="Sin publicaciones este mes">🕰️ sin actividad</span>'
    return ''

def _photo_candidates(band):
    return sorted((p for p in PHOTOS.glob(f'{safe(band)}_*.jpg') if p.stat().st_size > 5000),
                  key=lambda p: p.stat().st_size, reverse=True)

def photo_b64(band, shortcode):
    path = PHOTOS / f'{safe(band)}_{shortcode}.jpg'
    if path.exists() and path.stat().st_size > 5000:
        # Si la foto del post es un CARTEL y hay una FOTO de la banda mejor, priorízala.
        if _rank_for(band, path) >= 0.5:
            return 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode()
        return best_photo_b64(band)
    return logo_b64(band)


def best_photo_b64(band):
    cands = _photo_candidates(band)
    if not cands:
        return logo_b64(band)
    # Prioridad: fotos clasificadas como FOTO (score 1), luego neutras, luego CARTEL.
    best = max(cands, key=lambda c: (_rank_for(band, c), c.stat().st_size))
    return 'data:image/jpeg;base64,' + base64.b64encode(best.read_bytes()).decode()


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


def split_summary(text):
    """Separate the editorial activity lead from the supporting detail."""
    text = clean_caption(text)
    match = re.search(r'\.\s+(?=[A-ZÁÉÍÓÚÑÜ])', text)
    if not match:
        return text, ''
    return text[:match.end() - 1].strip(), text[match.end():].strip()


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
            r'<tr><td class="rank">.*?</td><td class="band-name">(.*?)</td>'
            r'<td class="listeners"><strong>(.*?)</strong>.*?</td>'
            r'<td style="color:var\(--muted\)">(.*?)</td>'
            r'<td><span class="([^"]+)">(.*?)</span></td></tr>')
        matches = pat.findall(text)
        if not matches:
            pat = re.compile(
                r'<tr><td class="rank">\d+</td><td class="band-name">(.*?)</td>'
                r'<td><strong>(.*?)</strong></td>'
                r'<td style="color:var\(--muted\)">(.*?)</td>'
                r'<td><span class="([^"]+)">(.*?)</span></td></tr>')
            matches = pat.findall(text)
        for band, now, q2, cls, arrow in matches:
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
# Radar de Medios: solo noticias relevantes a la escena folk metal (no todo
# el metal general de los 4 feeds). Se filtra por banda de la escena o keywords.
_SCENE_BANDS = {
    'saurom', 'mägo de oz', 'lepoka', 'lèpoka', 'celtian', 'salduie', 'dark moor',
    'celtibeerian', 'dunedain', 'dünedain', 'nidhögg', 'argion', 'lándevir', 'landevir',
    'reino de hades', 'el reno renardo', 'triskel', 'hadadanza', 'debler', 'daeria',
    'ekyrian', 'xeria', 'trovadorum', 'sovengar', 'kinnia', 'kaelis', 'khëlleden',
    'finnway', 'leyendärian', 'legacy of the seas', 'astter', 'aljamia'}
_SCENE_KW = ('folk metal', 'folk-metal', 'folk', 'celta', 'medieval', 'viking',
             'pagano', 'bardos', 'trol', 'leyendas del rock', 'rock imperium',
             'viña rock', 'mithril', 'hadas', 'folk rock')

def _news_relevant(n):
    t = (n['title'] or '').casefold()
    return any(b in t for b in _SCENE_BANDS) or any(k in t for k in _SCENE_KW)

news = [n for n in news if _news_relevant(n)][:8]
concert_rows = conn.execute(
    '''SELECT date, band_name, event_name, event_type, city, venue, source_url
       FROM concerts WHERE date >= ? AND date < ? AND band_name != 'Medio'
       ORDER BY date, band_name''',
     (next_month_date.strftime('%Y-%m-%d'), agenda_end_date.strftime('%Y-%m-%d'))).fetchall()
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
# Short or malformed editorial entries make the cards feel empty. Keep the
# source order: the editorial JSON already ranks the news by relevance.
highlights = [h for h in highlights
              if isinstance(h, dict) and clean_caption(h.get('text')) and
              len(clean_caption(h.get('text'))) >= 40][:6]
# Lo Gordo: orden conforme a las métricas (oyentes mensuales, M>K>raw).
# metrics se carga después (load_metrics); se reordena en el punto de render.
def _hl_metric_key(h, metrics_map):
    m = metrics_map.get(h.get('band', ''), ('0', '0', '', 'flat'))
    return parse_metric(m[0])
_HL_METRIC_SORTED = False

# Agenda: detailed calendar for next month, compact lists for the following
# three months. Events outside this window were deliberately not queried.
events = defaultdict(list)
for r in concert_rows:
    events[(r['date'] or '')[:10]].append(r)
calendar_month = next_month_date.strftime('%Y-%m')
first = next_month_date.date().replace(day=1)
last_day = calendar.monthrange(next_month_date.year, next_month_date.month)[1]
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


def compact_event_label(r):
    location = ' — '.join(p for p in (r['city'], r['venue']) if p)
    return location or r['event_name'] or 'Fecha anunciada'


def event_icon(t):
    return {'festival': '🎪', 'gira': '🗺️', 'concierto': '🎸'}.get(t or '', '🎸')


def event_class(t):
    value = (t or 'concierto').lower()
    return value if value in ('festival', 'gira', 'concierto') else 'concierto'


def month_label(value):
    return MONTH_NAMES[value.month - 1].capitalize() + f' {value.year}'


metrics = load_metrics(band_names)
# Lo Gordo: orden conforme a las métricas (oyentes mensuales, M>K>raw).
highlights.sort(key=lambda h: _hl_metric_key(h, metrics), reverse=True)
style_text = f'{CSS}{MODERN_CSS}{EDITORIAL_CSS}{WIDE_CSS}'.replace('hl-feature', 'legacy-feature').replace('hl-side', 'legacy-side')

parts = ['<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
         f'<title>Folk Metal Magazine · {month_name} {month_date.year}</title>',
          f'<style>{style_text}</style></head><body>']

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

# 2. Nav (Radar solo si hay noticias suficientes)
nav_parts = ['<nav class="section-nav">',
             '<a href="#indice">Índice</a><span>·</span>',
             '<a href="#gordo">🔥 Lo Gordo</a><span>·</span>',
             '<a href="#agenda">📅 Agenda</a><span>·</span>',
             '<a href="#bandas">⚔️ Bandas</a><span>·</span>']
if len(news) >= 2:
    nav_parts.append('<a href="#radar">📰 Radar</a><span>·</span>')
nav_parts.append('<a href="#metricas">📊 Métricas</a><span>·</span>')
nav_parts.append('<a href="../historias/index.html">📜 Historias</a></nav>')
parts.append(''.join(nav_parts))

parts.append('<main class="container">')

# 3. Índice
parts.append('<section id="indice"><div class="section-divider"><h2>Índice de Bandas</h2></div>')
parts.append('<div class="toc-grid">')
for i, band in enumerate(band_names, 1):
    parts.append(f'<div class="toc-card"><a href="#b-{eid(band)}">'
                 f'<img src="{logo_b64(band)}" alt="Logo {esc(band)}">'
                 f'<span class="toc-num">#{i:02d}</span>{esc(band)}</a>'
                 f'<a class="toc-hist" href="../historias/{hslug(band)}.html" target="_blank" rel="noopener">📜</a></div>')
parts.append('</div></section>')

# 4. Lo Gordo
parts.append('<section id="gordo"><div class="section-divider"><h2>🔥 Lo Gordo del Mes</h2></div>')
parts.append('<p class="lead">Los hechos más relevantes de la escena: retiradas, lanzamientos, cambios de formación y giras internacionales. Selección editorial basada en las publicaciones oficiales de cada banda.</p>')
if highlights:
    parts.append('<div class="gordo-grid">')
    for index, h in enumerate(highlights):
        img = photo_b64(h.get('band', ''), h.get('shortcode', ''))
        text = clean_caption(h.get('text') or '')
        if len(text) > 360:
            text = text[:357].rsplit(' ', 1)[0] + '…'
        tile = ('tile-a', 'tile-b', 'tile-c', 'tile-d')[index % 4]
        # Alturas de foto variadas (layout revista): patrón rítmico
        ph = ('ph-xl', 'ph-lg', 'ph-md', 'ph-lg', 'ph-md', 'ph-xl')[index % 6]
        parts.append(
            f'<article class="hl-card"><img class="{tile} {ph}" src="{img}" alt="Foto {esc(h["band"])}">'
             f'<div class="hl-body"><div class="hl-band">{h.get("emoji", "🔥")} {esc(h["band"])}</div>'
             f'<div class="hl-text">{esc(text)}</div>'
             f'<a class="hist-inline" href="../historias/{hslug(h.get("band", ""))}.html" target="_blank" rel="noopener">📜 Historia completa</a></div></article>')
    parts.append('</div>')
else:
    parts.append('<p class="empty-state">No hubo publicaciones que cumplieran los criterios.</p>')
parts.append('</section>')

# 5. Agenda
parts.append('<section id="agenda"><div class="section-divider"><h2>📅 Agenda de Conciertos</h2></div>')
parts.append('<p class="lead">Próximas fechas confirmadas de la escena. El calendario detallado corresponde al mes siguiente; los meses posteriores se listan de forma compacta.</p>')
parts.append(f'<h3 class="agenda-month">{esc(month_label(next_month_date))}</h3>')
parts.append('<div class="calendar"><div class="cal-head">' +
             ''.join(f'<div>{d}</div>' for d in ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do']) + '</div>')
for cell_index in range(start_offset + last_day):
    if cell_index % 7 == 0:
        parts.append('<div class="cal-row">')
    day_num = cell_index - start_offset + 1
    if day_num < 1 or day_num > last_day:
        parts.append('<div class="cal-cell cal-empty"></div>')
    else:
        date_key = f'{calendar_month}-{day_num:02d}'
        ev_html = []
        for r in events.get(date_key, []):
            label = event_label(r)
            link = r['source_url'] or '#'
            kind = event_class(r['event_type'])
            ev_html.append(f'<div class="cal-event event-{kind}"><span class="event-badge">{event_icon(r["event_type"])} {esc(kind)}</span>'
                           f'<strong><a href="../historias/{hslug(r["band_name"])}.html" target="_blank" rel="noopener">{esc(r["band_name"])}</a></strong><br>'
                           f'<a href="{esc(link)}" target="_blank" rel="noopener">{esc(label)} 🔗</a></div>')
        parts.append(f'<div class="cal-cell"><div class="cal-day">{day_num}</div>{"".join(ev_html)}</div>')
    if cell_index % 7 == 6:
        parts.append('</div>')
if (start_offset + last_day) % 7:
    for _ in range(7 - ((start_offset + last_day) % 7)):
        parts.append('<div class="cal-cell cal-empty"></div>')
    parts.append('</div>')
parts.append('</div>')
for offset in range(1, 4):
    later = (next_month_date.replace(day=28) + timedelta(days=32 * offset)).replace(day=1)
    later_key = later.strftime('%Y-%m')
    later_events = [r for r in concert_rows if (r['date'] or '').startswith(later_key)]
    if not later_events:
        continue
    parts.append(f'<div class="agenda-later"><h3>{esc(month_label(later))}</h3>')
    for r in later_events:
        kind = event_class(r['event_type'])
        day = (r['date'] or '')[8:10].lstrip('0') or '0'
        label = compact_event_label(r)
        link = r['source_url'] or '#'
        parts.append(f'<div class="agenda-line event-{kind}"><span class="event-badge">{event_icon(r["event_type"])} {esc(kind)}</span>'
                     f'<span><strong>{esc(day)} {esc(MONTH_NAMES[later.month - 1])}</strong> — <a href="../historias/{hslug(r["band_name"])}.html" target="_blank" rel="noopener">{esc(r["band_name"])}</a>'
                     f' <span class="agenda-detail">({esc(label)})</span></span>'
                     f' <a href="{esc(link)}" target="_blank" rel="noopener">🔗</a></div>')
    parts.append('</div>')
parts.append('</section>')

# 6. Todas las Bandas
parts.append('<section id="bandas"><div class="section-divider"><h2>⚔️ Todas las Bandas</h2></div>')
parts.append('<div class="band-grid">')
for band_index, band in enumerate(band_names):
    rows = bands[band]
    metric = metrics.get(band)
    metric_html = ''
    if metric:
        now, q2, arrow, cls = metric
        metric_html = f'<div class="metrics">🎧 {esc(now)} <span class="{esc(cls)}">{esc(arrow)}</span> ' \
                      f'<span class="count">Q2: {esc(q2)}</span></div>'
    summary_txt = summaries_txt.get(band) or rule_summary(band, rows)
    metric_value = parse_metric(metric[0]) if metric else -1
    wide = band_index % 5 == 2 and (len(rows) >= 2 or metric_value >= 100000)
    layout_class = (' wide' if wide else '') + (' reverse' if band_index % 2 else '')
    summary_lead, summary_body = split_summary(summary_txt)
    tile = 'tile-a' if band_index % 2 == 0 else 'tile-b'
    summary_html = f'<div class="band-lead">{esc(summary_lead)}</div>'
    if summary_body:
        summary_html += f'<div class="band-body">{esc(summary_body)}</div>'
    parts.append(f'<article class="band-card-wrapper{layout_class}" id="b-{eid(band)}">'
                 f'<a class="top-link" href="#indice">↑ índice</a>'
                 f'<div class="band-card"><div class="band-header">'
                 f'<img class="{tile}" src="{best_photo_b64(band)}" alt="Foto {esc(band)}">'
                 f'<div><div class="name">{esc(band)}{status_badge(band)}</div>{metric_html}'
                 f'<div class="count">{len(rows)} publicaciones</div>'
                 f'<div class="hist-link"><a href="../historias/{hslug(band)}.html" target="_blank" rel="noopener">📜 Historia completa</a></div></div></div>'
                 f'<div class="band-summary">{summary_html}</div>')
    for p in rows:
        cap = clean_caption(p['caption'])
        if len(cap) > 300:
            cap = cap[:297].rsplit(' ', 1)[0] + '…'
        klass = 'post-item collapsed'
        date = (p['post_date'] or '')[:10]
        link = p['post_url'] or f'https://www.instagram.com/p/{p["shortcode"]}/'
        parts.append(f'<div class="{klass}"><span class="post-date">{esc(date)}</span>{esc(cap)} '
                     f'<span class="post-link"><a href="{esc(link)}" target="_blank" rel="noopener">🔗</a></span></div>')
    if rows:
        card_id = f'b-{eid(band)}'
        parts.append(f'<div class="more-row" role="button" tabindex="0" onclick="togglePosts(\'{card_id}\')" onkeydown="if(event.key===\'Enter\'||event.key===\' \')togglePosts(\'{card_id}\')">▼ ver publicaciones ({len(rows)})</div>')
    parts.append('</div></article>')
parts.append('</div></section>')

# 7. Radar de Medios (solo si hay noticias suficientes de la escena)
if len(news) >= 2:
    parts.append('<section id="radar"><div class="section-divider"><h2>📰 Radar de Medios</h2></div>')
    parts.append('<p class="lead">Noticias de la escena folk metal recogidas de los medios especializados (Hellpress, Metalcry, RafaBasa, The Dark Melody) durante el periodo.</p>')
    parts.append('<div class="news-list">')
    for news_index, n in enumerate(news):
        title = clean_caption(n['title'])
        card_class = 'news-card featured' if news_index == 0 else 'news-card'
        parts.append(f'<article class="{card_class}"><span class="news-source">{esc(n["source"])} · '
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
metric_max = max((parse_metric(metrics.get(b, ('—', '—', '—', 'flat'))[0]) for b in metric_bands), default=1)
metric_max = max(metric_max, 1)
for i, band in enumerate(metric_bands, 1):
    now, q2, arrow, cls = metrics.get(band, ('—', '—', '→', 'flat'))
    value = parse_metric(now)
    width = max(0, min(100, round(value / metric_max * 100))) if value >= 0 else 0
    medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, '')
    parts.append(f'<tr><td class="rank">{medal}<span>{i:02d}</span></td><td class="band-name"><a class="hist-inline" href="../historias/{hslug(band)}.html" target="_blank" rel="noopener">{esc(band)}</a></td>'
                 f'<td class="listeners"><strong>{esc(now)}</strong><div class="bar-track"><div class="bar" style="width:{width}%"></div></div></td><td style="color:var(--muted)">{esc(q2)}</td>'
                 f'<td><span class="{esc(cls)}">{esc(arrow)}</span></td></tr>')
parts.append('</tbody></table></section>')

# 9. Footer
parts.append(f'</main><footer><a href="#indice">↑ Volver al índice</a><br><br>'
             f'Folk Metal Magazine · {month_name} {month_date.year}<br>'
             f'{len(posts)} publicaciones de Instagram · {len(news)} noticias RSS mostradas · '
             f'contenido enlazado a sus fuentes originales</footer>')

parts.append('''<script>
function togglePosts(cardId) {
  var card = document.getElementById(cardId);
  if (!card) return;
  var posts = card.querySelectorAll('.post-item');
  var button = card.querySelector('.more-row');
  var isClosed = posts.length && posts[0].classList.contains('collapsed');
  posts.forEach(function(post) { post.classList.toggle('collapsed', !isClosed); });
  if (button) button.textContent = isClosed ? '▲ ocultar publicaciones' : '▼ ver publicaciones (' + posts.length + ')';
}
</script>''')
parts.append('</body></html>')

OUT.write_text(''.join(parts), encoding='utf-8')
print(f'Generated {OUT} | posts={len(posts)} bands={len(band_names)} '
      f'news={len(news)} events={len(concert_rows)} bytes={OUT.stat().st_size}')
