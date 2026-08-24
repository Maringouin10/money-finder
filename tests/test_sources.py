"""Mapping « réponse plateforme -> Model », sur des échantillons réels."""

from __future__ import annotations

import json
import unittest

from scraper.config import Settings
from scraper.sources import (CrealityCloudSource, MakerWorldSource,
                             PrintablesSource, ThingiverseSource)
from scraper.sources.nuxt import devalue_parse

from . import fixtures as fx


class FakeHttp:
    """Client HTTP factice : rejoue des réponses figées et enregistre les appels."""

    def __init__(self, get_json=None, post_json=None, text=""):
        self._get_json = get_json or {}
        self._post_json = post_json or {}
        self._text = text
        self.calls: list[tuple[str, str, dict]] = []

    def _match(self, table, url):
        if callable(table):
            return table(url)
        for key, value in table.items():
            if key in url:
                return value
        raise AssertionError(f"aucune réponse figée pour {url}")

    def get_json(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._match(self._get_json, url)

    def post_json(self, url, json=None, **kwargs):
        self.calls.append(("POST", url, {"json": json, **kwargs}))
        return self._match(self._post_json, url)

    def get_text(self, url, **kwargs):
        self.calls.append(("GET_TEXT", url, kwargs))
        return self._text


def settings(**kwargs) -> Settings:
    return Settings(**kwargs)


class TestMakerWorld(unittest.TestCase):
    def test_search_uses_design2_and_offset(self):
        http = FakeHttp(get_json={"select/design2": fx.MAKERWORLD_SEARCH})
        source = MakerWorldSource(settings(), http)
        models = source.search("fidget", 1)

        self.assertEqual(len(models), 1)
        method, url, kwargs = http.calls[0]
        self.assertIn("/search-service/select/design2", url)
        self.assertEqual(kwargs["params"]["offset"], 0)
        self.assertNotIn("page", kwargs["params"])

        m = models[0]
        self.assertEqual(m.source_id, "1755208")
        self.assertEqual(m.title, "My 10 star fidget design")
        self.assertEqual(m.url, "https://makerworld.com/en/models/1755208")
        self.assertEqual(m.creator, "BigDeX")
        self.assertEqual(m.creator_url, "https://makerworld.com/en/@user_2175937239")
        self.assertEqual(m.downloads, 125065)      # pas collectionCount
        self.assertEqual(m.likes, 19894)
        self.assertEqual(m.published_at, "2025-09-01")
        self.assertEqual(m.license.code, "SDFL")
        self.assertEqual(m.license.sellable, "no")
        self.assertEqual(m.description, "")        # absent de la recherche

    def test_enrich_reads_summary_and_model_files(self):
        http = FakeHttp(get_json={"select/design2": fx.MAKERWORLD_SEARCH,
                                  "design-service/design/": fx.MAKERWORLD_DETAIL})
        source = MakerWorldSource(settings(), http)
        model = source.search("fidget", 1)[0]
        source.enrich(model)

        self.assertIn("ten pointed star", model.description)
        self.assertEqual(model.license.code, "CC-BY-SA")       # code nu "BY-SA"
        self.assertEqual(model.license.sellable, "conditions")
        names = [f.name for f in model.files]
        self.assertEqual(names, ["10 STAR FIDGET TOY.stl", "star_v2.stl"])  # dossier aplati
        self.assertEqual(model.files[0].size, 418684)
        self.assertEqual(model.files[0].url, model.url)        # modelUrl vide -> page modèle


class TestPrintables(unittest.TestCase):
    def test_search_query_uses_offset_and_unquoted_enums(self):
        http = FakeHttp(post_json={"graphql": fx.PRINTABLES_SEARCH})
        source = PrintablesSource(settings(), http)
        models = source.search("fidget", 1)

        payload = http.calls[0][2]["json"]
        self.assertIn("printType: print", payload["query"])
        self.assertIn("ordering: best_match", payload["query"])
        self.assertNotIn("cursor", payload["query"])
        self.assertEqual(payload["variables"]["offset"], 0)

        m = models[0]
        self.assertEqual(m.source_id, "928")
        self.assertEqual(
            m.url, "https://www.printables.com/model/928-yet-another-fidget-infinity-cube-v2")
        self.assertEqual(m.creator, "Austin Vojta")
        self.assertEqual(m.creator_url, "https://www.printables.com/@austinvojta")
        self.assertEqual(m.image,
                         "https://media.printables.com/media/prints/928/images/cover.jpg")
        self.assertEqual(m.license.code, "CC-BY-SA")
        self.assertEqual(m.license_raw, "CC-BY-SA")   # abbreviation, pas name
        self.assertEqual(m.tags, ["fidget", "cube"])

    def test_detail_query_has_no_invalid_filepath(self):
        http = FakeHttp(post_json={"graphql": fx.PRINTABLES_SEARCH})
        source = PrintablesSource(settings(), http)
        model = source.search("fidget", 1)[0]

        http._post_json = {"graphql": fx.PRINTABLES_DETAIL}
        source.enrich(model)

        detail_query = http.calls[-1][2]["json"]["query"]
        stl_block = detail_query.split("stls {")[1].split("}")[0]
        self.assertNotIn("filePath", stl_block)

        self.assertIn("Buy a printed fidget cube", model.description)
        self.assertEqual([f.name for f in model.files],
                         ["yafic_v2_rounded.stl", "yafic_v2_02mm_pla_mk3.gcode"])
        self.assertTrue(model.files[0].url.endswith("/files"))


class TestCrealityCloud(unittest.TestCase):
    def test_search_posts_smart_search(self):
        http = FakeHttp(post_json={"smart_search": fx.CREALITY_SEARCH})
        source = CrealityCloudSource(settings(), http)
        models = source.search("fidget", 1)

        method, url, kwargs = http.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/api/cxy/smart_search/v1/model", url)
        self.assertEqual(kwargs["json"], {"keyword": "fidget", "page": 1, "pageSize": 1})

        m = models[0]
        self.assertEqual(m.title, "Fidget EGG")            # groupName
        self.assertEqual(m.creator, "BondFire")            # userInfo.nickName
        self.assertEqual(m.image, "https://pic2-cdn.creality.com/comp/model/cover.webp")
        self.assertEqual(m.published_at, "2026-03-18")     # epoch -> date
        self.assertEqual(m.license.code, "CXY-SL")
        self.assertEqual(m.license.sellable, "no")
        self.assertEqual(m.url,
                         "https://www.crealitycloud.com/model-detail/69bb0989f6b153ff3e656293")

    def test_enrich_reads_nuxt_payload(self):
        html = ('<html><script type="application/json" id="__NUXT_DATA__">'
                + json.dumps(fx.CREALITY_NUXT_PAYLOAD) + "</script></html>")
        http = FakeHttp(post_json={"smart_search": fx.CREALITY_SEARCH}, text=html)
        source = CrealityCloudSource(settings(), http)
        model = source.search("fidget", 1)[0]
        source.enrich(model)

        self.assertIn("Easter egg fidget", model.description)
        self.assertEqual(model.tags, ["fidget"])
        self.assertEqual([f.name for f in model.files], ["Fidget EGG"])
        self.assertEqual(model.files[0].size, 10824774)

    def test_devalue_resolves_references(self):
        parsed = devalue_parse(fx.CREALITY_NUXT_PAYLOAD)
        self.assertEqual(parsed["data"]["groupName"], "Fidget EGG")
        self.assertEqual(parsed["data"]["covers"][0]["url"],
                         "https://pic2-cdn.creality.com/comp/model/cover.webp")

    def test_devalue_survives_cycles(self):
        # 0 -> {"self": 1}, 1 -> {"back": 0}
        self.assertIsInstance(devalue_parse([{"self": 1}, {"back": 0}]), dict)


class TestThingiverse(unittest.TestCase):
    def _source(self):
        http = FakeHttp(get_json={
            "/search/": fx.THINGIVERSE_SEARCH,
            "/files": fx.THINGIVERSE_FILES,
            "/things/929504": fx.THINGIVERSE_DETAIL,
        })
        return ThingiverseSource(settings(thingiverse_token="x"), http), http

    def test_requires_token(self):
        ok, reason = ThingiverseSource(settings(), FakeHttp()).available()
        self.assertFalse(ok)
        self.assertIn("THINGIVERSE_TOKEN", reason)

    def test_search_does_not_fake_downloads_with_collect_count(self):
        source, _ = self._source()
        m = source.search("fidget", 1)[0]
        self.assertEqual(m.downloads, 0)          # absent du hit, surtout pas 10201
        self.assertEqual(m.likes, 8194)
        self.assertEqual(m.published_at, "2015-07-17")   # created_at
        self.assertEqual(m.license.sellable, "unknown")  # licence absente du hit

    def test_enrich_fills_license_downloads_and_direct_files(self):
        source, _ = self._source()
        model = source.search("fidget", 1)[0]
        source.enrich(model)

        self.assertEqual(model.license.code, "CC-BY-NC-SA")
        self.assertEqual(model.license.sellable, "no")
        self.assertEqual(model.downloads, 88583)
        self.assertEqual(model.tags, ["fidget"])
        # URL CDN directe issue de zip_data, pas le /download authentifié
        self.assertEqual(model.files[0].url,
                         "https://cdn.thingiverse.com/assets/mathgrrl_fidgetstar.scad")
        self.assertEqual(model.files[0].size, 13547)


if __name__ == "__main__":
    unittest.main()
