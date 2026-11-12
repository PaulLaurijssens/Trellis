import unittest

from app import llm


class LlmParameterTests(unittest.TestCase):
    def test_reasoning_models_drop_unsupported_temperature(self):
        params = llm.litellm.get_optional_params(
            model="gpt-5.5",
            custom_llm_provider="openai",
            temperature=0.2,
        )

        self.assertTrue(llm.litellm.drop_params)
        self.assertNotIn("temperature", params)


if __name__ == "__main__":
    unittest.main()