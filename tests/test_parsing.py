import unittest

from scraper.sources.base import as_int, as_text, first_records, pick


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

    def test_first_records_ignores_unrelated_lists(self):
        payload = {"tags": [{"slug": "x"}], "hits": [{"designId": 7, "title": "t"}]}
        records = first_records(payload, ("id", "designId"), ("title", "name"))
        self.assertEqual(records, [{"designId": 7, "title": "t"}])


if __name__ == "__main__":
    unittest.main()
