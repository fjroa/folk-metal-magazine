#!/usr/bin/env python3
"""store_monthly_extracts.py — Consolida el editorial mensual en la DB.

Cada mes, folk_editorial.py escribe media/summaries_{MONTH}.json con summaries,
facts y highlights. Este script hace UPSERT de ese contenido en la tabla
monthly_extracts de ~/.hermes/folk_metal_posts.db, de modo que el histórico
sobrevive aunque el JSON se pierda y las fichas históricas pueden acumular
contexto mes a mes.

Tabla:
  monthly_extracts(id, band_name, month UNIQUE(band_name,month),
                   summary, facts_json, highlights_json, stored_at)

Uso: python3 scripts/store_monthly_extracts.py [YYYY-MM]
     (sin argumento: procesa TODOS los media/summaries_*.json existentes)
"""
import json, sqlite3, sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = Path.home() / '.hermes' / 'folk_metal_posts.db'
MEDIA = REPO / 'media'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS monthly_extracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    band_name TEXT NOT NULL,
    month TEXT NOT NULL,
    summary TEXT,
    facts_json TEXT,
    highlights_json TEXT,
    stored_at TEXT,
    UNIQUE(band_name, month)
);
'''


def process_month(conn, month):
    path = MEDIA / f'summaries_{month}.json'
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'  ⚠️ {path.name}: JSON inválido ({e})')
        return 0
    summaries = data.get('summaries') or {}
    facts = data.get('facts') or {}
    highlights = data.get('highlights') or []
    now = datetime.now().isoformat(timespec='seconds')
    n = 0
    # Los highlights se indexan por banda para consulta rápida.
    hl_by_band = {}
    for h in highlights:
        b = h.get('band')
        if b:
            hl_by_band.setdefault(b, []).append(h)
    for band, text in summaries.items():
        if not text:
            continue
        conn.execute(
            '''INSERT INTO monthly_extracts
               (band_name, month, summary, facts_json, highlights_json, stored_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(band_name, month) DO UPDATE SET
                 summary=excluded.summary,
                 facts_json=excluded.facts_json,
                 highlights_json=excluded.highlights_json,
                 stored_at=excluded.stored_at''',
            (band, month, text,
             json.dumps(facts.get(band, []), ensure_ascii=False),
             json.dumps(hl_by_band.get(band, []), ensure_ascii=False),
             now))
        n += 1
    conn.commit()
    return n


def main():
    conn = sqlite3.connect(DB)
    conn.execute(SCHEMA)
    conn.commit()
    months = sys.argv[1:] if len(sys.argv) > 1 else \
        sorted(p.stem.replace('summaries_', '') for p in MEDIA.glob('summaries_*.json'))
    total = 0
    for month in months:
        n = process_month(conn, month)
        total += n
        print(f'  {month}: {n} bandas consolidados')
    conn.close()
    print(f'store_monthly_extracts: {total} extractos en monthly_extracts ({DB})')


if __name__ == '__main__':
    main()
