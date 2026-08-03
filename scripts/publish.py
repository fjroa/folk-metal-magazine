#!/usr/bin/env python3
"""publish.py — Orquestador mensual de la revista.

python3 scripts/publish.py YYYY-MM

Pasos (subprocess, prints numerados):
  1) Descarga caché de fotos y logos (folk_media_fetch.py)
  2) Genera editorial LLM (folk_editorial.py)  [si falla, continúa]
  3) Construye la edición HTML standalone (build_v16.py)
  4) Actualiza index.html con/a la card de la edición (sin duplicados)
  5) git add -A, commit, push origin master
  6) Verifica HTTP 200 en GitHub Pages (espera ~30s si publica)
"""
import re, subprocess, sys, time, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EDICIONES = REPO / 'ediciones'
INDEX = REPO / 'index.html'


def run(step, cmd):
    print(f'\n=== Paso {step}: {cmd} ===', flush=True)
    res = subprocess.run(cmd, cwd=REPO)
    if res.returncode != 0:
        print(f'  [warn] paso {step} terminó con código {res.returncode}', flush=True)
    return res.returncode


def month_label(month):
    import datetime
    y, m = month.split('-')
    names = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    return f'{names[int(m)-1].capitalize()} {y}'


def update_index(month, bands, posts, news, events):
    html = INDEX.read_text(encoding='utf-8')
    label = month_label(month)
    href = f'ediciones/{month}.html'
    card = (
        f'<a class="edition-card" href="{href}">\n'
        f'  <div class="edition-month">{label}</div>\n'
        f'  <div class="edition-title">Número #{month.split("-")[1]} · {label}</div>\n'
        f'  <div class="edition-desc">Resumen mensual verificable de la escena folk metal española: '
        f'publicaciones oficiales, agenda, radar de medios y métricas de Spotify.</div>\n'
        f'  <div class="edition-meta">\n'
        f'    <span>🎸 {bands} bandas</span>\n'
        f'    <span>📸 {posts} publicaciones</span>\n'
        f'    <span>📅 {events} eventos</span>\n'
        f'    <span>📰 RSS + Instagram</span>\n'
        f'  </div>\n'
        f'</a>\n'
    )
    placeholder_comment = '<!-- Dynamically populated by publish script -->'
    if re.search(rf'href="{re.escape(href)}"', html):
        # Reemplazar la card existente para este href (evita duplicados).
        pattern = rf'<a class="edition-card"[^>]*href="{re.escape(href)}".*?</a>\s*'
        new_html, n = re.subn(pattern, '', html, flags=re.S)
        if n:
            html = new_html
    # Insertar antes del comentario placeholder (o al final de #editions-list) si no está.
    if re.search(rf'href="{re.escape(href)}"', html):
        pass
    else:
        if placeholder_comment in html:
            html = html.replace(placeholder_comment, card + placeholder_comment, 1)
        else:
            html = re.sub(r'(<div class="editions"[^>]*>\s*)', r'\1' + card, html, count=1)
    INDEX.write_text(html, encoding='utf-8')
    print(f'  index.html actualizado con card {href} '
          f'(bandas={bands} posts={posts} eventos={events})', flush=True)


def main():
    if len(sys.argv) < 2:
        from datetime import datetime, timedelta
        month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    else:
        month = sys.argv[1]

    run(1, ['python3', 'scripts/folk_media_fetch.py', month])
    run(2, ['python3', 'scripts/folk_editorial.py', month])  # puede fallar; sigue igual
    # 2b) Persistir el editorial mensual en la DB (histórico de fichas).
    run(2, ['python3', 'scripts/store_monthly_extracts.py', month])
    # 2c) Regenerar fichas históricas por banda (siempre, aunque el editorial falle).
    run(2, ['python3', 'scripts/build_band_historias.py'])
    rc = run(3, ['python3', 'scripts/build_v16.py', month])

    # Parsear el report final de build_v16 para rellenar la card con stats reales.
    bands = posts = news = events = 0
    if rc == 0:
        out = EDICIONES / f'{month}.html'
        if out.exists():
            # Re-leer el último print del builder desde su salida no está disponible;
            # recalcular stats directamente desde la DB.
            try:
                import sqlite3
                conn = sqlite3.connect(Path.home() / '.hermes' / 'folk_metal_posts.db')
                conn.row_factory = sqlite3.Row
                posts = conn.execute(
                    "SELECT COUNT(*) FROM posts WHERE post_date LIKE ?", (month + '%',)).fetchone()[0]
                bands = conn.execute(
                    "SELECT COUNT(DISTINCT band_name) FROM posts WHERE post_date LIKE ?",
                    (month + '%',)).fetchone()[0]
                news = conn.execute(
                    "SELECT COUNT(*) FROM news_posts WHERE published LIKE ?", (month + '%',)).fetchone()[0]
                events = conn.execute(
                    "SELECT COUNT(*) FROM concerts WHERE date LIKE ? AND band_name != 'Medio'",
                    (month + '%',)).fetchone()[0]
                conn.close()
            except Exception as e:
                print(f'  [warn] no se pudieron recalcular stats: {e}', flush=True)
    update_index(month, bands, posts, news, events)

    run(4, ['git', 'add', '-A'])
    run(4, ['git', 'commit', '-m', f'Edición {month} · {month_label(month)}'])
    run(4, ['git', 'push', 'origin', 'master'])

    # 6) Verificación HTTP en GitHub Pages.
    url = f'https://fjroa.github.io/folk-metal-magazine/ediciones/{month}.html'
    print(f'\n=== Paso 6: verificación HTTP de {url} ===', flush=True)
    for attempt in range(12):  # hasta ~30s
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'folk-publish-check'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.getcode()
                print(f'  intento {attempt+1}: HTTP {status}', flush=True)
                if status == 200:
                    print('✓ Publicación verificada.', flush=True)
                    return
        except Exception as e:
            print(f'  intento {attempt+1}: {e}', flush=True)
        time.sleep(5)
    print('  [warn] no se obtuvo 200 tras varios intentos.', flush=True)


if __name__ == '__main__':
    main()
