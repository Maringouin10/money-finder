import unittest

from scraper.grouping import discover_groups, tag_duplicates
from scraper.models import Model


def model(title, source="thingiverse", idx="1"):
    return Model(source=source, source_id=f"{title}-{idx}", url="", title=title)


class TestGrouping(unittest.TestCase):
    def test_families_are_discovered_from_titles(self):
        titles = [
            "Infinity Cube fidget toy", "Infinity cube print in place",
            "INFINITY CUBE v2", "Planetary gear fidget", "Planetary Gear bearing",
            "planetary gears keychain", "Articulated dragon",
        ]
        groups = discover_groups([model(t, idx=str(i)) for i, t in enumerate(titles)], min_size=3)
        labels = [g.label for g in groups]
        self.assertIn("Infinity Cube", labels)
        self.assertIn("Planetary Gear", labels)
        self.assertEqual(groups[0].size, 3)
        self.assertEqual(labels[-1], "Divers / modèles isolés")

    def test_plural_and_case_are_merged(self):
        titles = ["Fidget slider", "fidget sliders", "SLIDER fidget toy"]
        groups = discover_groups([model(t, idx=str(i)) for i, t in enumerate(titles)], min_size=3)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].size, 3)

    def test_generic_words_never_become_a_family(self):
        titles = ["Fidget toy A", "Fidget toy B", "Fidget toy C", "Fidget toy D"]
        groups = discover_groups([model(t, idx=str(i)) for i, t in enumerate(titles)], min_size=3)
        self.assertEqual([g.slug for g in groups], ["divers"])

    def test_min_size_is_respected(self):
        titles = ["Gear cube one", "Gear cube two", "Something else"]
        groups = discover_groups([model(t, idx=str(i)) for i, t in enumerate(titles)], min_size=3)
        self.assertEqual([g.slug for g in groups], ["divers"])

    def test_cross_platform_duplicates_are_tagged(self):
        a = model("Infinity Cube", source="printables")
        b = model("infinity cube!", source="makerworld")
        tag_duplicates([a, b])
        self.assertEqual(a.also_on, ["MakerWorld"])
        self.assertEqual(b.also_on, ["Printables"])


if __name__ == "__main__":
    unittest.main()
