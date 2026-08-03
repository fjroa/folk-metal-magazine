#!/usr/bin/env python3
"""merge_band_data.py — Unifica perfiles curados + briefs investigados.

El panel de admin (futuro) gestionará UN solo archivo: data/bands.json.
Este script lo genera fusionando:
  - data/band_profiles.json (vault: conexiones, estudios, web, instagram, hitos)
  - data/band_briefs.json  (Metal Archives/Wikipedia: discografía completa, fuentes)

Reglas de merge:
  - campos del perfil (conexiones, estudios, web, instagram) tienen prioridad
    si existen; los del brief rellenan huecos.
  - discografia: la del brief (MA completa) si tiene >=3; si no, la del perfil.
  - hitos: se unen ambos (dedup por fecha+texto).
  - fuentes: solo del brief (URLs de verificación).

Salida: data/bands.json  { band: {origen, formada, genero, sello, web,
  instagram, miembros[], discografia[], hitos[], conexiones[], estudios[],
  fuentes[], wiki} }

Uso: python3 scripts/merge_band_data.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROFILES_PATH = REPO / 'data' / 'band_profiles.json'
BRIEFS_PATH = REPO / 'data' / 'band_briefs.json'
OUT_PATH = REPO / 'data' / 'bands.json'

LIST_FIELDS = ('miembros', 'conexiones', 'estudios', 'fuentes')
SCALAR_FIELDS = ('origen', 'formada', 'genero', 'sello', 'web', 'instagram', 'wiki')


def dedup_hitos(items):
    seen, out = set(), []
    for h in items or []:
        key = (str(h.get('fecha', '')), str(h.get('texto', '')).strip().lower())
        if key in seen or not h.get('texto'):
            continue
        seen.add(key)
        out.append(h)
    return out


def main():
    profiles = json.loads(PROFILES_PATH.read_text(encoding='utf-8'))
    profiles.pop('meta', None)
    briefs = json.loads(BRIEFS_PATH.read_text(encoding='utf-8'))
    bands = {}
    all_names = sorted(set(profiles) | set(briefs), key=str.casefold)
    for band in all_names:
        p = profiles.get(band, {})
        b = briefs.get(band, {})
        entry = {}
        # Escalares: perfil gana, brief rellena
        for f in SCALAR_FIELDS:
            entry[f] = p.get(f) or b.get(f) or ''
        # Listas: se unen con dedup
        for f in LIST_FIELDS:
            merged = []
            for src in (p, b):
                for item in src.get(f) or []:
                    if item not in merged:
                        merged.append(item)
            entry[f] = merged
        # Discografía: MA completa (brief) > perfil
        b_discs = b.get('discografia') or []
        p_discs = p.get('discografia') or []
        if len(b_discs) >= 3:
            vault_by_title = {str(d.get('titulo', '')).strip().lower(): d
                              for d in p_discs}
            merged_discs = []
            for d in b_discs:
                key = str(d.get('titulo', '')).strip().lower()
                v = vault_by_title.get(key)
                merged_discs.append({**d, 'nota': v.get('nota', '') if v else ''})
            entry['discografia'] = merged_discs
        else:
            entry['discografia'] = p_discs or b_discs
        # Hitos: unión con dedup
        entry['hitos'] = dedup_hitos(list((p.get('hitos') or [])) + list((b.get('hitos') or [])))
        bands[band] = entry
    OUT_PATH.write_text(json.dumps(bands, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'merge_band_data: {len(bands)} bandas → {OUT_PATH}')
    for band, e in sorted(bands.items()):
        fields = sum(1 for f in SCALAR_FIELDS if e.get(f)) + \
                 sum(1 for f in LIST_FIELDS if e.get(f))
        print(f'  {band}: {fields}/{len(SCALAR_FIELDS)+len(LIST_FIELDS)} campos, '
              f'{len(e.get("discografia") or [])} discos')


if __name__ == '__main__':
    main()
