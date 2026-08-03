import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))

from build_band_historias import clean_caption, slug
_argv = sys.argv
sys.argv = ['build_v16.py', '2026-07']
from build_v16 import clean_caption as magazine_clean_caption, hslug, parse_metric
sys.argv = _argv
from folk_editorial import band_context, band_known_releases, extract_facts


class FolkMagazineTests(unittest.TestCase):
    def test_slug_ascii(self):
        self.assertEqual(slug('Lándevir'), 'landevir')
        self.assertEqual(slug('Mägo de Oz'), 'mago-de-oz')
        self.assertEqual(slug('Khëlleden'), 'khelleden')
        self.assertEqual(slug('Reino de Hades'), 'reino-de-hades')

    def test_hslug_matches_build_historias(self):
        statuses = json.loads((REPO / 'media' / 'band_status.json').read_text(encoding='utf-8'))
        self.assertEqual(len(statuses), 29)
        for band in statuses:
            self.assertEqual(hslug(band), slug(band))

    def test_clean_caption(self):
        self.assertEqual(magazine_clean_caption('&amp; #039;'), "'")
        self.assertEqual(magazine_clean_caption('a&nbsp;&amp;b'), 'a&b')

    def test_parse_metric(self):
        self.assertEqual(parse_metric('3.8M'), 3800000)
        self.assertEqual(parse_metric('254.8K'), 254800)
        self.assertEqual(parse_metric('890'), 890)
        self.assertEqual(parse_metric(''), -1)

    def test_extract_facts_anti_anacronismo(self):
        rows = [{'caption': 'Adelanto: «JUNTO A TI», videoclip disponible.'}]
        facts = extract_facts('Reino de Hades', rows)
        self.assertNotIn('Publicó o adelantó «junto a ti».', facts)
        self.assertTrue(any('videoclip' in fact.lower() for fact in facts))

    def test_band_known_releases(self):
        self.assertIn('junto a ti', band_known_releases('Reino de Hades'))

    def test_band_context_no_anacronismo(self):
        context = band_context('Reino de Hades')
        self.assertIn('Junto a Ti', context)
        self.assertIn('2025', context)

    def test_build_historias_outputs(self):
        if not (Path.home() / '.hermes' / 'folk_metal_posts.db').exists():
            raise unittest.SkipTest('No existe la DB real')
        import build_band_historias

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(build_band_historias, 'HISTORIAS', Path(tmp)):
                build_band_historias.main()
            files = list(Path(tmp).glob('*.html'))
            self.assertTrue((Path(tmp) / 'index.html').exists())
            fichas = [path for path in files if path.name != 'index.html']
            self.assertGreaterEqual(len(fichas), 29)
            for ficha in fichas:
                self.assertIn('<!DOCTYPE html', ficha.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
