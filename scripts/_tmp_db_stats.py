#!/usr/bin/env python3
"""Quick DB stats for folk metal magazine."""
import sqlite3, sys
db = sqlite3.connect('/home/roa/.hermes/folk_metal_posts.db')
checks = [
    ("posts 2026-08", "SELECT COUNT(*) FROM posts WHERE post_date LIKE '2026-08%'"),
    ("news 2026-08", "SELECT COUNT(*) FROM news_posts WHERE published LIKE '2026-08%'"),
    ("concerts 2026-08", "SELECT COUNT(*) FROM concerts WHERE date LIKE '2026-08%'"),
    ("posts 2026-07", "SELECT COUNT(*) FROM posts WHERE post_date LIKE '2026-07%'"),
    ("news 2026-07", "SELECT COUNT(*) FROM news_posts WHERE published LIKE '2026-07%'"),
    ("concerts 2026-07", "SELECT COUNT(*) FROM concerts WHERE date LIKE '2026-07%'"),
    ("total posts", "SELECT COUNT(*) FROM posts"),
    ("total news", "SELECT COUNT(*) FROM news_posts"),
    ("total concerts", "SELECT COUNT(*) FROM concerts"),
    ("total monthly_extracts", "SELECT COUNT(*) FROM monthly_extracts"),
]
for name, q in checks:
    try:
        print(f"{name}: {db.execute(q).fetchone()[0]}")
    except Exception as e:
        print(f"{name}: ERROR {e}")
print("bands aug:", [r[0] for r in db.execute("SELECT DISTINCT band_name FROM posts WHERE post_date LIKE '2026-08%' ORDER BY band_name")])
print("last post date:", db.execute("SELECT MAX(post_date) FROM posts").fetchone()[0])
print("last news date:", db.execute("SELECT MAX(published) FROM news_posts").fetchone()[0])
