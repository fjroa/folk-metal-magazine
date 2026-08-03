# Folk Metal Magazine — repo de la revista

Revista mensual de la escena folk metal española. Publicada en GitHub Pages:
https://fjroa.github.io/folk-metal-magazine/ediciones/YYYY-MM.html

## Arquitectura

- **DB (fuente de datos, solo lectura):** `~/.hermes/folk_metal_posts.db` (SQLite)
  - `posts(id, band_name, handle, shortcode UNIQUE, post_date, caption, image_url, post_url, ...)` — Instagram, mes = `post_date LIKE 'YYYY-MM%'`
  - `news_posts(source, title, url UNIQUE, published, ...)` — RSS medios, mes = `published LIKE 'YYYY-MM%'`
  - `concerts(band_name, event_name, event_type, date, city, venue, source_url, ...)` — agenda estructurada, mes = `date LIKE 'YYYY-MM%'`
- **Caché de medios (persistente, gitignored):** `media/photos/{safe}_{shortcode}.jpg` (400x300 jpg), `media/logos/{safe}.png` (200x200 png). `safe()` = nombre de banda normalizado (ä→a, ë→e, ö→o, è→e, ü→u, espacios→_).
- **Editorial (generado por LLM local):** `media/summaries_{MONTH}.json`
  - `{"month": "...", "summaries": {band: texto_periodístico}, "facts": {band: [hechos]}, "highlights": [{"band","emoji","text","post_url","shortcode"}]}`
- **Scripts:**
  - `scripts/folk_media_fetch.py` — descarga fotos (og:image) y logos (perfil IG). SECUENCIAL (IG rate-limita concurrencia).
  - `scripts/folk_editorial.py` — extrae hechos verificados por banda y pide redacción al LLM local :8888 → summaries JSON.
  - `scripts/build_v16.py` — builder determinista HTML standalone (ESTE es el script a mantener/crear).
  - `scripts/publish.py` — orquestador: media → editorial → build → git push → verificación HTTP.

## Convenciones

- Python 3 stdlib SOLO (sin pip install). ImageMagick `convert` disponible para imágenes.
- Salida en español (es-ES). HTML standalone con imágenes base64 embebidas.
- `python3 scripts/build_v16.py YYYY-MM` → escribe `ediciones/YYYY-MM.html`.
- Mes por defecto si no se pasa: mes anterior.
- Los IDs de anclas quitan diéresis (ä→a...) pero conservan á,é,í,ó,ú,ñ.

## Secciones del HTML (en orden)

1. **Portada** — gradiente oscuro, "FOLK METAL MAGAZINE", "Edición mensual · {Mes Año}", fuentes, stats (N publicaciones, N bandas, N noticias).
2. **Nav** — Índice · 🔥 Lo Gordo · 📅 Agenda · ⚔️ Bandas · 📊 Métricas.
3. **Índice** — grid de bandas con logo (28-32px) + número + nombre → `#b-{id}`.
4. **Lo Gordo** — tarjetas desde `summaries[highlights]`: foto del post (media/photos/{safe}_{shortcode}.jpg, fallback logo) 100x92 + banda + texto periodístico + 🔗.
5. **Agenda** — calendario del mes completo, semana Lu→Do, celdas vacías en blanco, eventos = emoji tipo + banda + label + 🔗. Tabla `concerts`.
6. **Todas las Bandas** — grid 2 col. Header: foto (best photo `media/photos/{safe}_*.jpg`, fallback logo, fallback SVG letra) 74x74 + nombre + métricas + nº posts. `band-summary` itálico desde `summaries[band]`. Posts: fecha + caption (≤360) + 🔗; 3 visibles, resto colapsado "▼ ver todas (N)".
7. **Radar de Medios** — lista news_posts: fuente · fecha + título 🔗.
8. **Métricas** — tabla ordenada numéricamente (M>K>raw), columnas # Banda Oyentes Q2 Δ con clases up/down/flat. Fuente: parsear edición anterior `ediciones/{prev}.html` si existe; si no, defaults hardcodeados (los de build_v15).
9. **Footer** — ↑ volver al índice + créditos.

## Estilo visual (pergamino, NO oscuro salvo portada)

Ver `scripts/build_v15_reference.py` para el CSS completo (variables parchment, cover dark, calendar, band cards, hl-card, metrics-table, toc-grid, section-divider, section-nav, more-row JS). Mantener ese lenguaje visual.
