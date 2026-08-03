# SPEC: v17 — Enlaces a fichas históricas en todas las secciones + tests

Repo: ~/github/folk-metal-magazine (NO tocar nada fuera del repo)
Modelo: openrouter/openai/gpt-5.6-luna (configurado en ~/.config/opencode/opencode.json)

## Contexto

El proyecto genera una revista mensual de la escena folk metal española:
- `scripts/build_v16.py` — genera `ediciones/YYYY-MM.html` (revista, capa accesible)
- `scripts/build_band_historias.py` — genera `historias/{slug}.html` por banda (capa profunda)
- `scripts/folk_editorial.py` — editorial LLM con hechos verificados
- `data/band_profiles.json` + `data/band_briefs.json` — datos curados por banda
- `scripts/band_research.py` — investigación Metal Archives/Wikipedia
- `scripts/store_monthly_extracts.py` — persiste editorial en DB (tabla monthly_extracts)
- `historias/index.html` — índice de las 29 fichas

Los slugs de ficha usan `hslug(band)` en build_v16.py y `slug(band)` en
build_band_historias.py — ambos ASCII (ä→a, ü→u, á→a, ñ→n, etc). NO CAMBIAR.

## Tarea 1: Enlaces a ficha histórica en TODAS las secciones de build_v16.py

Actualmente solo hay enlaces en: nav (`../historias/index.html`), TOC (icono 📜)
y card de banda (`📜 Historia completa`).

FALTAN — añadir enlace a la ficha de la banda en:

1. **Lo Gordo** (`<article class="hl-card">`): dentro de `.hl-body`, debajo del
   `.hl-text`, añadir:
   ```html
   <a class="hist-inline" href="../historias/{hslug(band)}.html" target="_blank" rel="noopener">📜 Historia completa</a>
   ```
   con la banda del highlight (`h.get('band','')`).

2. **Agenda — calendario** (`.cal-event`): el `<strong>` contiene la banda.
   Envolver el nombre de la banda en un enlace a su ficha:
   ```html
   <strong><a href="../historias/{hslug(band)}.html" target="_blank" rel="noopener">{band}</a></strong>
   ```

3. **Agenda — lista compacta** (`.agenda-line`): el `<strong>` del día contiene
   la banda (`<strong>{esc(day)} {mes}</strong> — {band}`). Envolver SOLO el
   nombre de la banda en enlace a su ficha.

4. **Métricas** (`<td class="band-name">`): envolver el nombre de la banda en
   enlace a su ficha:
   ```html
   <td class="band-name"><a class="hist-inline" href="../historias/{hslug(band)}.html" target="_blank" rel="noopener">{band}</a></td>
   ```

Añadir CSS para `.hist-inline` (heredar estilo de `.hist-link a`, fuente 12.5px,
color accent, borde punteado dorado, hover gold) tanto en EDITORIAL_CSS como en
WIDE_CSS si hace falta. El CSS `.hist-link a` ya existe — reutilizarlo.

IMPORTANTE: respetar el orden de render actual, NO reordenar secciones.
El `<script>` togglePosts es string normal con .replace() — no tocar.

## Tarea 2: Tests pytest

Crear `tests/` en el repo con pytest (usar unittest-style o pytest plain, sin
deps externas — solo stdlib + los módulos del repo).

Archivo: `tests/test_folk_magazine.py`

Tests obligatorios:

1. `test_slug_ascii`: slug('Lándevir') == 'landevir', slug('Mägo de Oz') == 'mago-de-oz',
   slug('Khëlleden') == 'khelleden', slug('Reino de Hades') == 'reino-de-hades'.
2. `test_hslug_matches_build_historias`: para las 29 bandas de band_status.json,
   hslug(band) == slug(band) (importar ambos módulos).
3. `test_clean_caption`: clean_caption('&amp; #039;') == "'" (comillas rotas RSS),
   clean_caption('a&nbsp;&amp;b') → 'a&b' (espacios colapsados).
4. `test_parse_metric`: parse_metric('3.8M') == 3800000, parse_metric('254.8K') == 254800,
   parse_metric('890') == 890, parse_metric('') == -1.
5. `test_extract_facts_anti_anacronismo`: con captions de Reino de Hades julio 2026
   (contienen "JUNTO A TI" + "videoclip"), extract_facts NO produce
   'Publicó o adelantó «junto a ti».' y SÍ produce un hecho con 'videoclip'.
   Datos: el brief de Reino de Hades en data/band_briefs.json tiene «Junto a Ti» (2025).
6. `test_band_known_releases`: band_known_releases('Reino de Hades') incluye
   'junto a ti' como clave (extraído de la nota 'Adelanto: «Junto a Ti» (2025)').
7. `test_band_context_no_anacronismo`: band_context('Reino de Hades') contiene
   'Junto a Ti' y '2025' (el LLM no debe presentarlo como novedad).
8. `test_build_historias_outputs`: ejecutar build_band_historias.main() con
   monkeypatch de HISTORIAS a un tmp_path, verificar que genera index.html y
   al menos 29 fichas .html, y que cada ficha contiene '<!DOCTYPE html'.

Para los tests que necesitan la DB real (~/.hermes/folk_metal_posts.db), usar
try/except sqlite3.Error y `pytest.skip` si no existe. NO crear DBs falsas.

Ejecutar con: `python3 -m pytest tests/ -q` (comprobar que pytest está instalado;
si no, `python3 -m unittest discover tests` como fallback — diseñar los tests
para que funcionen con unittest también, usando solo asserts).

## Tarea 3: Verificación

1. `python3 -m pytest tests/ -q` → todos PASS
2. `python3 scripts/build_band_historias.py` → 29 fichas + index.html
3. `python3 scripts/build_v16.py 2026-07` → ediciones/2026-07.html generado
4. Verificar con grep que ediciones/2026-07.html contiene
   `../historias/reino-de-hades.html` y `../historias/saurom.html`
   y que el número de enlaces `../historias/` es >= 60.

## Reglas

- NO modificar scripts/folk_editorial.py ni scripts/build_band_historias.py
  (ya funcionan; solo importarlos para tests).
- NO tocar data/band_briefs.json ni data/band_profiles.json.
- NO ejecutar folk_editorial.py (llama al LLM; caro). Solo importar funciones.
- NO commitear. Solo dejar los cambios en working tree.
- Reportar al final: archivos modificados, resultado de tests, grep verificado.
