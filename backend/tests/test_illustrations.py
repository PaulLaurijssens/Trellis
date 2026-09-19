import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("illustrations", Path(__file__).resolve().parents[1] / "app/illustrations.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class IllustrationTests(unittest.TestCase):
    def test_valid_flow_preserves_only_declared_content(self):
        value = {"type":"flow", "title":"Attention", "nodes":[{"id":"q","label":"Query"},{"id":"s","label":"Scores"}], "edges":[{"from":"q","to":"s","label":"compare"}], "script":"alert(1)"}
        valid = module.validate(value)
        self.assertNotIn("script",valid)
        self.assertEqual(valid["edges"][0]["from"],"q")
        value["edges"][0]["to"]="missing"
        self.assertIsNone(module.validate(value))

    def test_nonfinite_and_boolean_numbers_rejected(self):
        for bad in [float("nan"), float("inf"), True, "2", 101, 10**1000]:
            self.assertIsNone(module.validate({"type":"vectors","title":"Example", "vectors":[{"label":"q","x":bad,"y":1},{"label":"k","x":2,"y":1}]}))

    def test_comparison_and_bars_are_bounded(self):
        self.assertIsNotNone(module.validate({"type":"comparison","title":"Compare","columns":[{"label":"A","items":["First"]},{"label":"B","items":["Second"]}]}))
        self.assertIsNone(module.validate({"type":"bars","title":"Example","items":[{"label":"A","value":-1},{"label":"B","value":2}]}))
        self.assertIsNone(module.validate({"type":"html","title":"Unsafe","html":"<script/>"}))

    def test_visual_context_survives_for_followup_and_memory(self):
        message={"content":"Compare these vectors.","illustration":{"type":"vectors","title":"Worked example","vectors":[{"label":"q","x":1,"y":2},{"label":"k","x":2,"y":1}]}}
        self.assertIn('"x": 2',module.message_context(message))
        self.assertEqual(message["content"],"Compare these vectors.")
        self.assertEqual(module.message_context({"content":"Plain answer"}),"Plain answer")

    def test_malformed_flow_endpoint_is_omitted(self):
        self.assertIsNone(module.validate({"type":"flow","title":"Example","nodes":[{"id":"a","label":"A"},{"id":"b","label":"B"}],"edges":[{"from":[],"to":"b"}]}))
