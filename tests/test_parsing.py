import unittest

from scraper.sources.base import as_int, as_text, first_records, pick, records_at


class TestTolerantParsing(unittest.TestCase):
    def test_pick_first_existing_path(self):
        data = {"cover": {"url": "https://img"}, "title": "x"}
        self.assertEqual(pick(data, "coverUrl", "cover.url"), "https://img")
        self.assertEqual(pick(data, "missing", default="-"), "-")

    def test_as_text_handles_nested_shapes(self):
        self.assertEqual(as_text({"name": "CC-BY"}), "CC-BY")
        self.assertEqual(as_text(["a", "b"]), "a, b")
        self.assertEqual(as_int("42"), 42)
        self.assertEqual(as_int(None), 0)

    def test_first_records_finds_nested_result_list(self):
        payload = {"data": {"result": {"cursor": "c", "items": [
            {"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}}}
        records = first_records(payload, ("id",), ("name", "title"))
        self.assertEqual([r["id"] for r in records], [1, 2])

    def test_records_at_beats_a_longer_unrelated_list(self):
        # cas réel Printables : `tags` est plus longue que `items`
        payload = {"data": {"result": {"items": [{"id": "928", "name": "cube",
                                                  "tags": [{"id": "1", "name": "fidget"},
                                                           {"id": "2", "name": "cube"}]}]}}}
        self.assertEqual(records_at(payload, "data.result.items")[0]["id"], "928")
        self.assertEqual(records_at(payload, "data.missing"), [])
        # l'heuristique, elle, se ferait piéger
        self.assertEqual(len(first_records(payload, ("id",), ("name",))), 2)

    def test_first_records_ignores_unrelated_lists(self):
        payload = {"tags": [{"slug": "x"}], "hits": [{"designId": 7, "title": "t"}]}
        records = first_records(payload, ("id", "designId"), ("title", "name"))
        self.assertEqual(records, [{"designId": 7, "title": "t"}])


if __name__ == "__main__":
    unittest.main()
