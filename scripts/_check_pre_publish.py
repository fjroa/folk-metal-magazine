#!/usr/bin/env python3
"""Chequeo rápido DB + bands.json (validación pre-publish)."""
import sqlite3, json, sys
from pathlib import Path

conn = sqlite3.connect('/home/roa/.hermes/folk_metal_posts.db')
conn.row_factory = sqlite3.Row
for month in ('2026-07', '2026-08'):
    posts = conn.execute("SELECT COUNT(*) FROM posts WHERE post_date LIKE ?", (month + '%',)).fetchone()[0]
    bands = conn.execute("SELECT COUNT(DISTINCT band_name) FROM posts WHERE post_date LIKE ?", (month + '%',)).fetchone()[0]
    news = conn.execute("SELECT COUNT(*) FROM news_posts WHERE published LIKE ?", (month + '%',)).fetchone()[0]
    events = conn.execute("SELECT COUNT(*) FROM concerts WHERE date LIKE ? AND band_name != 'Medio'", (month + '%',)).fetchone()[0]
    print(f"{month}: posts={posts} bands={bands} news={news} concerts={events}")

print("--- próximos conciertos (ago-oct) ---")
for r in conn.execute("SELECT band_name,event_name,date,city FROM concerts WHERE date >= '2026-08-01' AND date < '2026-11-01' ORDER BY date LIMIT 12"):
    print(dict(r))
conn.close()

print("--- bands.json ---")
with open('/home/roa/github/folk-metal-magazine/data/bands.json') as f:
    bands = json.load(f)
print("bandas:", len(bands))
missing = [b for b, v in bands.items() if 'metricas' not in v or 'spotify_discografia' not in v.get('metricas', {})]
print("sin spotify_discografia:", missing)
for b, v in list(bands.items())[:2]:
    print(b, "| metricas keys:", list(v.get('metricas', {}).keys()))
