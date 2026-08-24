import unittest

from scraper.licenses import Sellable, normalize


class TestLicenses(unittest.TestCase):
    def check(self, raw, code, sellable):
        info = normalize(raw)
        self.assertEqual(info.code, code, raw)
        self.assertEqual(info.sellable, sellable.value, raw)

    def test_creative_commons(self):
        self.check("Creative Commons - Attribution", "CC-BY", Sellable.YES)
        self.check("CC-BY-SA", "CC-BY-SA", Sellable.CONDITIONS)
        self.check("Creative Commons - Attribution - No Derivatives", "CC-BY-ND", Sellable.CONDITIONS)
        self.check("CC BY-NC", "CC-BY-NC", Sellable.NO)
        self.check("Attribution-NonCommercial-NoDerivs", "CC-BY-NC-ND", Sellable.NO)

    def test_public_domain(self):
        self.check("CC0 1.0 Universal", "CC0", Sellable.YES)
        self.check("Creative Commons - Public Domain Dedication", "CC0", Sellable.YES)

    def test_proprietary(self):
        self.check("Standard Digital File License", "SDFL", Sellable.NO)
        self.check("All Rights Reserved", "SDFL", Sellable.NO)
        self.check("BSDL-1.1", "BSDL", Sellable.NO)

    def test_software_licenses(self):
        self.check("GPL-3.0", "GPL-3.0", Sellable.CONDITIONS)
        self.check("MIT", "MIT", Sellable.YES)

    def test_missing(self):
        info = normalize(None)
        self.assertEqual(info.sellable, Sellable.UNKNOWN.value)
        self.assertIn("vérifier", info.note.lower())

    def test_unrecognised_keeps_raw(self):
        info = normalize("Licence maison v3")
        self.assertEqual(info.sellable, Sellable.UNKNOWN.value)
        self.assertEqual(info.raw, "Licence maison v3")


if __name__ == "__main__":
    unittest.main()
