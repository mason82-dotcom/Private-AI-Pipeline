"""Cheap offline structural regression checks for the release contract."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_project_roadmap_and_security_documents_exist(self):
        for name in ('docs/ROADMAP.md', 'docs/PRODUCT_DESIGN.md',
                     'docs/SECURITY.md', 'AGENTS.md', '.github/workflows/ci.yml'):
            self.assertGreater((ROOT / name).stat().st_size, 200)

    def test_readme_states_actual_version_and_known_limits(self):
        text = (ROOT / 'README.md').read_text(encoding='utf8')
        self.assertIn('v0.3', text)
        self.assertIn('nicht', text.lower())
        self.assertIn('Light Console', text)
        self.assertIn('MCP_READONLY=true', text)

    def test_compose_does_not_publish_gateway_or_enable_passthrough(self):
        text = (ROOT / 'compose.yaml').read_text()
        self.assertIn('internal: true', text)
        self.assertIn("ENABLE_OPENAI_API_PASSTHROUGH: 'false'", text)
        self.assertIn("ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS: 'false'", text)
        self.assertNotIn('8000:8000', text)

    def test_gitignore_contains_secret_paths(self):
        lines = (ROOT / '.gitignore').read_text().splitlines()
        for secret in ('.env', '*.sqlite3', 'backups/'):
            self.assertIn(secret, lines)


if __name__ == '__main__':
    unittest.main()
