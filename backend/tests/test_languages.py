import unittest

from pydantic import BaseModel, ValidationError

from app import languages


class LanguageTests(unittest.TestCase):
    def test_english_is_the_default_and_unknown_codes_fall_back(self):
        self.assertEqual(languages.DEFAULT, "en")
        self.assertEqual(languages.name("en"), "English")
        self.assertEqual(languages.name("xx"), "English")

    def test_requests_accept_only_installed_languages(self):
        class Body(BaseModel):
            language: languages.Code = "en"
        self.assertEqual(Body(language="en").language, "en")
        with self.assertRaises(ValidationError):
            Body(language="xx")

    def test_detects_english_but_never_claims_another_language(self):
        self.assertEqual(languages.detect("Can you explain this with an example?"), "en")
        self.assertIsNone(languages.detect("Peux-tu m'expliquer le mécanisme d'attention avec un exemple simple?"))
        self.assertIsNone(languages.detect("ok"))

    def test_mentor_follows_a_language_trellis_does_not_know(self):
        from app import chat
        rule = chat.language_rule(None, "en")
        self.assertIn("language of the learner's last message", rule)
        self.assertIn("English", rule)

    def test_lessons_from_another_install_still_load(self):
        from test_teach_model import m, manifest
        self.assertEqual(m.manifest(manifest(language="nl"))["language"], "nl")
        with self.assertRaises(ValueError):
            m.manifest(manifest(language="<script>"))


if __name__ == "__main__":
    unittest.main()
