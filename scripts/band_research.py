#!/usr/bin/env python3
"""band_research.py — Brief biográfico verificable por banda.

Estrategia de contexto (regla del usuario, ago 2026): bandas con décadas de
trayectoria no se pueden resumir solo con posts de IG. Antes de que el LLM
editorial redacte sobre una banda, necesita un BRIEF de quién es esa banda:
origen, año de formación, discografía completa, miembros, sellos, cambios
históricos de formación. Este script investiga eso con fuentes públicas
(Metal Archives, Wikipedia) y guarda el resultado en data/band_briefs.json
con URL de fuente para cada dato — verificable, nunca inventado.

Flujo:
  1. Lee data/band_profiles.json (curado del vault) como base.
  2. Para cada banda sin perfil completo, busca en Metal Archives y Wikipedia.
  3. Escribe data/band_briefs.json {band: {origen, formada, genero, sello,
     discografia[], miembros[], hitos[], fuentes[]}}.
  4. El dato pasa al prompt de folk_editorial como contexto histórico.

Uso: python3 scripts/band_research.py [banda1 banda2 ...]   (sin args: todas)
Modo: --fetch  fuerza descarga web; sin él usa solo lo que ya está en el vault.
"""
import json, re, subprocess, sys
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parent.parent
PROFILES_PATH = REPO / 'data' / 'band_profiles.json'
BRIEFS_PATH = REPO / 'data' / 'band_briefs.json'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'

FETCH = '--fetch' in sys.argv
only = [a for a in sys.argv[1:] if not a.startswith('--')]


def http_get(url, timeout=25):
    """Fetch con curl (evita el TLS fingerprint de urllib que MA bloquea con 403)."""
    try:
        r = subprocess.run(
            ['curl', '-sL', '--max-time', str(timeout), '-A', UA,
             '-e', 'https://www.metal-archives.com/', url],
            capture_output=True, text=True, timeout=timeout + 10)
        return r.stdout
    except Exception as e:
        print(f'    ⚠️ curl {url[:60]}: {e}')
        return ''


def http_json(url):
    return http_get(url)


BANDS = [
    'Aljamia', 'Argion', 'Astter', 'Celtian', 'Celtibeerian', 'Daeria',
    'Dark Moor', 'Debler', 'Dünedain', 'Ekyrian', 'El Reno Renardo',
    'Finnway', 'Hadadanza', 'Kaelis', 'Khëlleden', 'Kinnia',
    'Legacy of the Seas', 'Leyendärian', 'Lándevir', 'Lèpoka', 'Mägo de Oz',
    'Nidhögg', 'Reino de Hades', 'Salduie', 'Saurom', 'Sovengar', 'Triskel',
    'Trovadorum', 'Xeria',
]


def search_ma(query):
    """Metal Archives search (JSON): devuelve {band_name, url} o None."""
    try:
        url = ('https://www.metal-archives.com/search/ajax-band-search/?'
               f'field=name&query={quote(query)}&limit=1')
        data = http_json(url)
        parsed = json.loads(data)
        rows = parsed.get('aaData') or []
        if not rows:
            return None
        first = rows[0][0] if isinstance(rows[0], list) else rows[0]
        m = re.search(r'href="([^"]+)"[^>]*>([^<]+)</a>', first)
        if m:
            return {'name': m.group(2).strip(), 'url': m.group(1)}
    except Exception as e:
        print(f'    ⚠️ MA search {query}: {e}')
    return None


def fetch_ma_band(url):
    """Metal Archives band page → datos básicos (tabla de la derecha)."""
    try:
        html_text = http_json(url)
        info = {}
        m = re.search(r'<dt>Country of origin:</dt>\s*<dd>(.*?)</dd>', html_text)
        if m:
            info['origen'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        m = re.search(r'<dt>Formed in:</dt>\s*<dd>(.*?)</dd>', html_text)
        if m:
            info['formada'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        m = re.search(r'<dt>Genre:</dt>\s*<dd>(.*?)</dd>', html_text)
        if m:
            info['genero'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        m = re.search(r'<dt>Label:</dt>\s*<dd>(.*?)</dd>', html_text)
        if m:
            info['sello'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # Discografía vía endpoint AJAX: /band/discography/id/{id}/tab/all
        mid = re.search(r'/bands/[^/]+/(\d+)', url)
        if mid:
            disc_url = f'https://www.metal-archives.com/band/discography/id/{mid.group(1)}/tab/all'
            disc_html = http_json(disc_url)
            discs = re.findall(
                r'<a[^>]+href="[^"]*albums?/[^"]*"[^>]*>([^<]+)</a>[\s\S]*?'
                r'<td[^>]*>(Full-length|EP|Single|Demo|Split)</td>[\s\S]*?'
                r'<td[^>]*>(\d{4})</td>',
                disc_html)
            info['discografia'] = [{'titulo': t.strip(), 'anio': int(a), 'tipo': k}
                                   for t, k, a in discs[:15]]
        return info
    except Exception as e:
        print(f'    ⚠️ MA band {url}: {e}')
        return {}


def search_wiki(query):
    """Wikipedia (API action=opensearch → extract)."""
    try:
        url = ('https://es.wikipedia.org/w/api.php?action=opensearch&format=json&'
               f'search={quote(query)}&limit=1')
        data = json.loads(http_json(url))
        if data and data[1]:
            title = data[1][0]
            extract_url = ('https://es.wikipedia.org/w/api.php?action=query&format=json&'
                           f'prop=extracts&exintro&explaintext&titles={quote(title)}')
            ex = json.loads(http_json(extract_url))
            pages = ex.get('query', {}).get('pages', {})
            for page in pages.values():
                return {'title': title, 'extract': page.get('extract', '')[:1200]}
    except Exception as e:
        print(f'    ⚠️ wiki {query}: {e}')
    return None


def main():
    profiles = json.loads(PROFILES_PATH.read_text(encoding='utf-8'))
    profiles = {k: v for k, v in profiles.items() if k != 'meta'}
    briefs = {}
    if BRIEFS_PATH.exists():
        try:
            briefs = json.loads(BRIEFS_PATH.read_text(encoding='utf-8'))
        except Exception:
            briefs = {}

    targets = only or BANDS
    for band in targets:
        prof = profiles.get(band, {})
        brief = briefs.get(band, {'fuentes': []})
        # 1. Base del vault (ya verificada)
        if prof.get('origen') and not brief.get('origen'):
            brief['origen'] = prof['origen']
        if prof.get('formada') and not brief.get('formada'):
            brief['formada'] = prof['formada']
        if prof.get('genero') and not brief.get('genero'):
            brief['genero'] = prof['genero']
        if prof.get('sello') and not brief.get('sello'):
            brief['sello'] = prof['sello']
        if prof.get('discografia') and not brief.get('discografia'):
            brief['discografia'] = prof['discografia']
        if prof.get('miembros') and not brief.get('miembros'):
            brief['miembros'] = prof['miembros']
        if prof.get('hitos') and not brief.get('hitos'):
            brief['hitos'] = prof['hitos']
        # 2. Investigación web: forzar con --fetch si falta el perfil base o si la
        #    discografía es pobre (<3) — bandas con décadas necesitan el catálogo
        #    completo de Metal Archives, no solo lo que hay en el vault.
        discs = brief.get('discografia') or []
        need = not (brief.get('origen') and brief.get('formada'))
        need = need or len(discs) < 3
        if FETCH and need:
            print(f'  🔎 {band}')
            ma = search_ma(band)
            if ma:
                info = fetch_ma_band(ma['url'])
                if info.get('origen'):
                    brief['origen'] = info['origen']
                if info.get('formada'):
                    try:
                        brief['formada'] = int(info['formada'])
                    except ValueError:
                        brief['formada'] = info['formada']
                if info.get('genero'):
                    brief['genero'] = info['genero']
                if info.get('sello'):
                    brief['sello'] = info['sello']
                # Discografía: MA es canónico cuando trae catálogo completo (>=3);
                # conserva las notas del vault fusionando por título.
                if info.get('discografia') and len(info['discografia']) >= 3:
                    vault_discs = {str(d.get('titulo', '')).strip().lower(): d
                                   for d in (prof.get('discografia') or [])}
                    merged = []
                    for d in info['discografia']:
                        key = str(d.get('titulo', '')).strip().lower()
                        v = vault_discs.get(key)
                        merged.append({**d, 'nota': v.get('nota', '') if v else ''})
                    brief['discografia'] = merged
                src = f'metal-archives: {ma["url"]}'
                if src not in brief.setdefault('fuentes', []):
                    brief['fuentes'].append(src)
            wk = search_wiki(band + ' banda')
            if wk and wk.get('extract'):
                brief.setdefault('wiki', wk['title'] + ': ' + wk['extract'][:600])
                src = f'wikipedia: {wk["title"]}'
                if src not in brief['fuentes']:
                    brief['fuentes'].append(src)
        briefs[band] = brief

    BRIEFS_PATH.write_text(json.dumps(briefs, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'band_research: {len(briefs)} briefs → {BRIEFS_PATH}')
    for b, br in sorted(briefs.items()):
        have = [k for k in ('origen', 'formada', 'discografia', 'miembros', 'sello') if br.get(k)]
        print(f'  {b}: {len(have)}/5 campos ({", ".join(have) or "vacío"})')


if __name__ == '__main__':
    main()
