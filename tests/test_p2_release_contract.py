"""P2 product/security contract; verifies that UI does not silently bypass safeguards."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class P2ReleaseContract(unittest.TestCase):
    def read(self,rel):return (ROOT/rel).read_text(encoding='utf-8')

    def test_gateway_and_console_use_separate_knowledge_capability(self):
        gateway=self.read('compose.yaml')
        console=self.read('compose.console.yaml')
        for text in (gateway,console):
            self.assertIn('KNOWLEDGE_TOKEN:',text)
            self.assertIn('KNOWLEDGE_IMPORT_ENABLED:',text)
        self.assertIn('KNOWLEDGE_NAMESPACE:',gateway)
        self.assertNotIn('KNOWLEDGE_NAMESPACE:',console)
        self.assertNotIn('ports:',gateway.split('  gateway:')[1].split('  webui:')[0])
        self.assertIn("internal: true",gateway)

    def test_ui_separates_documents_memory_and_escapes_all_untrusted_results(self):
        js=self.read('console/static/app.js')
        for expected in ('data-tab','Wissensdaten werden lokal geladen','/api/knowledge?',
                         'importText(file)','html(d.filename)','html(m.body)','html(r.excerpt)'):
            self.assertIn(expected,js)
        self.assertNotIn('KNOWLEDGE_TOKEN',js)
        self.assertNotIn('process.env.PIPELINE_TOKEN',js)

    def test_non_destructive_env_upgrade_and_off_by_default(self):
        upgrade=self.read('scripts/upgrade_env_p2.sh')
        self.assertIn('if key is None:',upgrade)
        self.assertIn('KNOWLEDGE_IMPORT_ENABLED=false',upgrade)
        self.assertIn('with p.open(\'a\'',upgrade)
        self.assertIn('KNOWLEDGE_IMPORT_ENABLED=false',self.read('.env.example'))
        self.assertIn('memory_data:',self.read('compose.yaml'))

if __name__=='__main__': unittest.main()
