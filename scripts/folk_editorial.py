#!/usr/bin/env python3
"""folk_editorial.py — Redacción periodística incremental con el LLM local.

1. Extrae HECHOS verificables por banda desde captions reales (scoped per banda).
2. Llama al LLM local (:8888, Fable 711) con contexto pequeño: hechos + URLs reales.
3. El LLM redacta 2-4 frases por banda y blurbs para Lo Gordo, SIN poder inventar
   datos que no estén en el JSON de hechos.
4. Escribe <repo>/media/summaries_{MONTH}.json consumido por build_v16.py.
   Si el LLM falla, usa fallback basado en reglas (hechos → frases).

Uso: python3 scripts/folk_editorial.py [YYYY-MM]
"""
import json, os, re, sqlite3, sys, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
DB = HOME / '.hermes' / 'folk_metal_posts.db'
OUTDIR = Path('/home/roa/github/folk-metal-magazine') / 'media'
LLM_URL = 'http://localhost:8888/v1/chat/completions'
LLM_MODEL = 'Qwen3.6-27B-Fable-Fusion-711-MTP-Q4_K_M.gguf'
OR_URL = 'https://openrouter.ai/api/v1/chat/completions'
OR_MODELS = ['poolside/laguna-s-2.1', 'deepseek/deepseek-v4-flash']
TIMEOUT = 90
LOCAL_TIMEOUT = 25  # si el local tarda más, saltamos a OpenRouter

if len(sys.argv) > 1:
    MONTH = sys.argv[1]
else:
    _first = datetime.now().replace(day=1)
    MONTH = (_first - timedelta(days=1)).strftime('%Y-%m')

OUTDIR.mkdir(parents=True, exist_ok=True)

# ── limpieza de captions ────────────────────────────────────────────────────
def clean(text):
    text = text or ''
    for pat, repl in [(r'&\s*#039\s*;', "'"), (r'&\s*#8217\s*;', "'"), (r'&\s*#39\s*;', "'"),
                      (r'&\s*amp\s*;', '&'), (r'&\s*quot\s*;', '"')]:
        text = re.sub(pat, repl, text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()

# ── extracción de hechos (algoritmo v11/v12, scoped por banda) ──────────────
JOKE_BLOCK = ['notice me, senpai', 'catarina', 'buenas noches', 'hasta luego', 'la vida es']
MUSIC_CTX = re.compile(r'single|álbum|album|disco|estrena|lanzamiento|canción|tema|videoclip|adelanto|cd|vinilo|ep\b', re.I)

def extract_facts(band, rows):
    all_text = ' '.join(clean(r['caption']) for r in rows).lower()
    facts = []
    # Lanzamientos: nombres entre comillas con contexto musical
    names = []
    for m in re.finditer(r'["“«\'‘]([^"”»\'’]{3,60})["”»\'’]', all_text):
        cand = m.group(1).strip()
        ctx = all_text[max(0, m.start() - 60):m.end() + 60]
        if not MUSIC_CTX.search(ctx):
            continue
        if any(j in cand.lower() for j in JOKE_BLOCK):
            continue
        if cand.lower() in ('vltreia', 'sobre el mar mmxxvi', 'sobre el mar'):
            cand = 'Sobre el Mar MMXXVI'
        names.append(cand)
    # dedup: mantener la variante más larga si hay subcadenas
    dedup = []
    for n in sorted(names, key=len, reverse=True):
        if not any(n.lower() in d.lower() and n.lower() != d.lower() for d in dedup):
            dedup.append(n)
    names = dedup[:3]
    if names:
        facts.append('Publicó o adelantó ' + '; '.join(f'«{n}»' for n in names) + '.')
    # Retirada / despedida
    if re.search(r'se retira|anuncia su retirada|deja los escenarios|adiós definitivo|último disco|nos despedimos', all_text):
        facts.append('Anunció su retirada o despedida de los escenarios.')
    # Producción
    if re.search(r'grabaci|estudio|producci|grabando|masteriz', all_text):
        facts.append('Está en pleno proceso de grabación o producción de nuevo material.')
    # Formación
    if re.search(r'deja la banda|dejar la banda|nuevo guitarrista|nuevo bater|nueva formación|incorpora a|se une a la banda', all_text):
        facts.append('Hubo movimiento en la formación del grupo.')
    # Festivales / directos (con nombre)
    fest = []
    for f in ['leyendas del rock', 'rock imperium', 'z! live rockfest', 'viña rock', 'resurrection fest', 'mekanika',
              'castellfolk', 'piorno rock', 'andalucía big fest', 'wacken', 'metalmanía']:
        if f in all_text:
            fest.append(f.title())
    if fest:
        facts.append('Confirmó presencia en ' + ', '.join(fest[:3]) + '.')
    elif re.search(r'concierto|directo|gira|escenario|festival', all_text):
        facts.append('Comunicó fechas de directo o actividad de gira.')
    # Internacional
    intl = []
    for c in ['mty', 'cdmx', 'monterrey', 'ciudad de méxico', 'argentina', 'colombia', 'méxico', 'mexico', 'italia', 'europa', 'alemania']:
        if c in all_text:
            intl.append(c)
    if intl:
        facts.append('La actividad tuvo dimensión internacional (' + ', '.join(intl[:3]) + ').')
    # Aniversarios
    if re.search(r'aniversario|25 años|20 años|30 años', all_text) and not re.search(r'cumpleaños', all_text):
        facts.append('Celebró un aniversario relevante del grupo.')
    # Entrevistas / prensa
    if re.search(r'entrevista|metal hammer|heavy metal radio|prensa', all_text):
        facts.append('Participó en entrevistas o apareció en prensa especializada.')
    return facts

def fallback_summary(band, facts):
    if facts:
        return ' '.join(facts[:3])
    return 'La banda mantuvo actividad en redes durante el periodo, principalmente con contenido visual y promocional. Cada publicación está enlazada a su fuente original para su verificación.'

# ── LLM (local primero; OpenRouter como fallback si el local va lento) ──────
def _or_key():
    try:
        txt = Path.home().joinpath('.hermes/.env').read_text()
        m = re.search(r'^OPENROUTER_API_KEY=(.*)$', txt, re.M)
        return m.group(1).strip() if m else ''
    except Exception:
        return ''

def _call(url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    msg = data.get('choices', [{}])[0].get('message', {})
    content = msg.get('content') or msg.get('text') or ''
    if not content:
        raise RuntimeError(f'respuesta sin contenido: {str(data)[:200]}')
    return content.strip()

def llm(prompt, max_tokens=1200, temperature=0.4):
    messages = [{'role': 'user', 'content': prompt}]
    # FOLK_LLM=openrouter salta el intento local (útil cuando el slot :8888
    # está ocupado por otra sesión Hermes: -np 1 → cola lenta).
    if os.environ.get('FOLK_LLM') != 'openrouter':
        # 1) Intento local (rápido, privado)
        try:
            body = json.dumps({'model': LLM_MODEL, 'messages': messages,
                               'max_tokens': max_tokens, 'temperature': temperature,
                               'stream': False}).encode()
            return _call(LLM_URL, {'Content-Type': 'application/json'}, body, LOCAL_TIMEOUT)
        except Exception as e:
            print(f'  [info] local lento/fallo ({e}); uso OpenRouter')
    # 2) Fallback OpenRouter con reintentos y varios modelos
    key = _or_key()
    if not key:
        raise RuntimeError('sin OPENROUTER_API_KEY')
    for attempt in range(3):
        for model in OR_MODELS:
            try:
                body = json.dumps({'model': model, 'messages': messages,
                                   'max_tokens': max_tokens, 'temperature': temperature,
                                   'stream': False}).encode()
                return _call(OR_URL, {'Content-Type': 'application/json',
                                      'Authorization': f'Bearer {key}'}, body, 60)
            except Exception as e:
                print(f'  [warn] OR {model} intento {attempt + 1}: {e}')
    raise RuntimeError('sin proveedor LLM disponible')

def llm_summary(band, facts, rows):
    post_lines = '\n'.join(
        f"- ({r['post_date'][:10]}) {clean(r['caption'])[:220]} [url: {r['post_url'] or 'https://www.instagram.com/p/' + r['shortcode'] + '/'}]"
        for r in rows[:6]
    )
    facts_txt = '\n'.join(f'- {f}' for f in facts) if facts else '(sin hechos destacados)'
    prompt = (
        'Eres redactor de la revista "Folk Metal Magazine", especializada en la escena folk metal española.\n'
        f'Redacta un resumen periodístico de la banda {band} para la edición de {MONTH}.\n'
        'REGLAS ESTRICTAS:\n'
        '1. USA ÚNICAMENTE los hechos verificados listados abajo. NO inventes nombres, discos, fechas ni datos.\n'
        '2. NO añadas nacionalidades, orígenes, ciudades ni datos que no estén en los HECHOS.\n'
        '3. Tono impersonal de periodista, en español. 2-4 frases.\n'
        '4. NO menciones números de publicaciones, métricas, ni "el grupo publicó X posts".\n'
        '5. No empieces con minúscula ni con frases sueltas.\n'
        f'HECHOS VERIFICADOS:\n{facts_txt}\n\n'
        f'PUBLICACIONES REALES DEL MES (para contexto, no las cites literalmente):\n{post_lines}\n\n'
        'RESUMEN:'
    )
    try:
        return llm(prompt)
    except Exception as e:
        print(f'  [warn] LLM falló para {band}: {e}')
        return fallback_summary(band, facts)

def llm_blurb(band, caption, post_url, date):
    prompt = (
        'Eres redactor de "Folk Metal Magazine". Escribe un titular-noticia periodístico (2-3 frases, español) '
        'sobre esta publicación verificada de una banda.\n'
        'REGLAS: usa solo la información del texto; tono de periodista; no inventes datos; no copies el texto literalmente.\n'
        f'Banda: {band} | Fecha: {date} | URL: {post_url}\n'
        f'Publicación:\n{clean(caption)[:600]}\n\n'
        'NOTICIA:'
    )
    try:
        return llm(prompt, max_tokens=800, temperature=0.5)
    except Exception as e:
        print(f'  [warn] LLM falló en blurb {band}: {e}')
        return clean(caption)[:220]

# ── highlights: solo eventos grandes (prioridad por keywords) ───────────────
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

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT band_name, shortcode, post_date, caption, post_url FROM posts WHERE post_date LIKE ? "
                        "ORDER BY band_name COLLATE NOCASE, post_date DESC", (MONTH + '%',)).fetchall()
    conn.close()
    bands = {}
    for r in rows:
        bands.setdefault(r['band_name'], []).append(r)

    summaries = {}
    for band, bro in bands.items():
        facts = extract_facts(band, bro)
        summaries[band] = {'text': llm_summary(band, facts, bro), 'facts': facts}
        print(f'  {band}: {len(facts)} hechos', flush=True)

    highlights = []
    seen = set()
    for h_band, emoji, kws in HIGHLIGHT_SPECS:
        if h_band not in bands or h_band in seen:
            continue
        found = False
        for kw in kws:
            for p in bands[h_band]:
                cap = clean(p['caption'])
                if re.search(kw, cap, re.I):
                    url = p['post_url'] or f'https://www.instagram.com/p/{p["shortcode"]}/'
                    highlights.append({'band': h_band, 'emoji': emoji, 'text': llm_blurb(h_band, cap, url, p['post_date']),
                                       'post_url': url, 'shortcode': p['shortcode']})
                    seen.add(h_band)
                    found = True
                    break
            if found:
                break

    out = {'month': MONTH, 'summaries': {b: v['text'] for b, v in summaries.items()},
           'facts': {b: v['facts'] for b, v in summaries.items()}, 'highlights': highlights}
    path = OUTDIR / f'summaries_{MONTH}.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nOK: {path} | bandas={len(summaries)} highlights={len(highlights)}')

if __name__ == '__main__':
    main()
