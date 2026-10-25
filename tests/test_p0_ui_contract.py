"""Static privacy and UX contract for the Light Console P0 app shell."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class UXContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT/'console/static/index.html').read_text()
        cls.css = (ROOT/'console/static/styles.css').read_text()
        cls.js = (ROOT/'console/static/app.js').read_text()

    def test_five_main_navigation_items_only(self):
        self.assertEqual(self.html.count('data-view='), 5)
        self.assertIn('Wissen &amp; Gedächtnis', self.html)
        self.assertNotIn('data-view="memory"', self.html)
        self.assertNotIn('data-view="models"', self.html)

    def test_system_and_knowledge_tabs_are_separate(self):
        self.assertIn("['documents','Dokumente']", self.js)
        self.assertIn("['memory','Erinnerungen']", self.js)
        for label in ('Dienste', 'Modelle', 'Netzwerk', 'Sicherungen', 'Einstellungen'):
            self.assertIn("'"+label+"'", self.js)

    def test_no_remote_assets_or_preview_fake_metrics(self):
        self.assertNotIn('https://', self.html + self.css)
        self.assertNotIn('localStorage.', self.js)
        self.assertNotIn('sessionStorage.', self.js)
        self.assertIn('kein Projektfilter', self.html)
        self.assertIn('noch nicht angebunden', self.js)

    def test_palette_keyboard_and_mobile_accessibility(self):
        self.assertIn('aria-labelledby="palette-title"', self.html)
        self.assertIn('aria-controls="rail"', self.html)
        self.assertIn('e.key.toLowerCase()', self.js)
        self.assertIn('aria-expanded', self.js)
        self.assertIn('44px', self.css)

    def test_sensitive_tools_are_informational_only(self):
        for value in ('READ', 'WRITE', 'EXEC', 'NETWORK'):
            self.assertIn(value, self.js)
        self.assertNotIn("fetch('/api/memory", self.js)
        self.assertNotIn("fetch('/api/tools", self.js)

if __name__ == '__main__': unittest.main()
