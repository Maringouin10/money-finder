"""Échantillons de réponses réelles (sonde API du 2026-08), tronqués.

Ils servent à figer le mapping « champ plateforme -> champ Model » : si une
API change de forme, ces tests échouent avant le scraping réel.
"""

MAKERWORLD_SEARCH = {
    "total": 4223,
    "hits": [{
        "id": 1755208,
        "title": "My 10 star fidget design",
        "slug": "my-10-star-fidget-design",
        "cover": "https://makerworld.bblmw.com/makerworld/model/design/cover.gif",
        "likeCount": 19894,
        "collectionCount": 52384,
        "printCount": 105539,
        "downloadCount": 125065,
        "designCreator": {"uid": 2175937239, "name": "BigDeX", "handle": "user_2175937239"},
        "createTime": "2025-09-01T17:32:53Z",
        "license": "Standard Digital File License",
        "tags": ["fidget", "Toy", "sensory"],
        "nsfw": False,
    }],
    "suggest": {"options": []},
}

MAKERWORLD_DETAIL = {
    "id": 1755208,
    "title": "My 10 star fidget design",
    "coverUrl": "https://makerworld.bblmw.com/design/cover.gif",
    "summary": "<p>A ten pointed star fidget</p>",
    "license": "BY-SA",
    "downloadCount": 125065,
    "tags": ["fidget", "Toy"],
    "instances": [{"id": 1866474, "title": "0.24mm layer, 1 walls, 10% infill"}],
    "designExtension": {"model_files": [
        {"modelName": "10 STAR FIDGET TOY.stl", "modelSize": 418684,
         "modelUrl": "", "modelType": "stl", "isDir": False, "children": []},
        {"isDir": True, "dirName": "variants", "children": [
            {"modelName": "star_v2.stl", "modelSize": 220000, "modelUrl": "",
             "modelType": "stl", "isDir": False, "children": []}]},
    ]},
}

PRINTABLES_SEARCH = {"data": {"result": {"totalCount": 10000, "items": [{
    "id": "928",
    "name": "Yet Another Fidget Infinity Cube v2",
    "slug": "yet-another-fidget-infinity-cube-v2",
    "summary": "v2 of my fidget cube features easier-to-print joints",
    "likesCount": 16440,
    "downloadCount": 154413,
    "datePublished": "2024-11-06T14:47:49.848916+00:00",
    "filesCount": 5,
    "image": {"id": "2246162", "filePath": "media/prints/928/images/cover.jpg"},
    "user": {"id": "957", "publicUsername": "Austin Vojta", "handle": "austinvojta",
             "verified": True},
    "license": {"id": "2", "name": "Creative Commons — Attribution  — Share Alike",
                "abbreviation": "CC-BY-SA", "disallowRemixing": False},
    "category": {"id": "33", "name": "Puzzles & Brain-teasers"},
    "tags": [{"id": "830", "name": "fidget"}, {"id": "942", "name": "cube"}],
}]}}}

PRINTABLES_DETAIL = {"data": {"print": {
    "id": "928",
    "name": "Yet Another Fidget Infinity Cube v2",
    "slug": "yet-another-fidget-infinity-cube-v2",
    "description": "<blockquote><h3>Buy a printed fidget cube</h3></blockquote>",
    "license": {"id": "2", "name": "Creative Commons — Attribution  — Share Alike",
                "abbreviation": "CC-BY-SA"},
    "user": {"id": "957", "publicUsername": "Austin Vojta", "handle": "austinvojta"},
    "image": {"id": "1", "filePath": "media/prints/928/images/cover.jpg"},
    "images": [{"id": "1", "filePath": "media/prints/928/images/cover.jpg", "name": "cover.jpg"}],
    "tags": [{"id": "830", "name": "fidget"}],
    "stls": [{"id": "7287", "name": "yafic_v2_rounded.stl", "fileSize": 5988884,
              "folder": "", "note": "rounded edges", "order": 0}],
    "slas": [],
    "otherFiles": [],
    "gcodes": [{"id": "2047", "name": "yafic_v2_02mm_pla_mk3.gcode", "fileSize": 5491809}],
}}}

CREALITY_SEARCH = {"code": 0, "msg": "ok", "result": {"count": 1000, "list": [{
    "id": "69bb0989f6b153ff3e656293",
    "shareId": "81284373",
    "createTime": 1773865353,
    "userId": 4988294105,
    "groupName": "Fidget EGG",
    "covers": [{"url": "https://pic2-cdn.creality.com/comp/model/cover.webp",
                "type": 2, "width": 1200, "height": 1600,
                "originUrl": "https://pic2-cdn.creality.com/common/origin.jpeg"}],
    "pcCovers": [{"url": "https://pic2-cdn.creality.com/upload/anim.gif", "type": 0}],
    "userInfo": {"userId": 4988294105, "nickName": "BondFire", "level": 7},
    "license": "CXY-SL",
    "likeCount": 1089,
    "downloadCount": 6515,
    "urlAlias": "fidget-egg-3d-printing",
}]}}

# Payload Nuxt (devalue) : tableau plat, l'entrée 0 est la racine.
CREALITY_NUXT_PAYLOAD = [
    {"data": 1},                                                    # 0
    {"groupName": 2, "groupDesc": 3, "license": 4,                  # 1
     "model3mfList": 5, "covers": 9, "tags": 12, "downloadZip": 15},
    "Fidget EGG",                                                   # 2
    "<p>Fun Easter egg fidget!</p>",                                # 3
    "CXY-SL",                                                       # 4
    [6],                                                            # 5
    {"name": 7, "size": 8},                                         # 6
    "Fidget EGG",                                                   # 7
    10824774,                                                       # 8
    [10],                                                           # 9
    {"url": 11},                                                    # 10
    "https://pic2-cdn.creality.com/comp/model/cover.webp",          # 11
    [13],                                                           # 12
    {"name": 14},                                                   # 13
    "fidget",                                                       # 14
    "",                                                             # 15
]

THINGIVERSE_SEARCH = {"total": 10000, "hits": [{
    "id": 929504,
    "name": "Fidget Star",
    "url": "https://api.thingiverse.com/things/929504",
    "public_url": "https://www.thingiverse.com/thing:929504",
    "created_at": "2015-07-17T03:09:52+00:00",
    "thumbnail": "https://cdn.thingiverse.com/assets/fidget_star_lots.jpg",
    "preview_image": "https://resize.thingiverse.com/?url=cover",
    "creator": {"id": 1, "name": "mathgrrl",
                "public_url": "https://www.thingiverse.com/mathgrrl"},
    "like_count": 8194,
    "collect_count": 10201,
    "tags": [{"name": "fidget", "tag": "fidget"}],
}]}

THINGIVERSE_DETAIL = {
    "id": 929504,
    "name": "Fidget Star",
    "public_url": "https://www.thingiverse.com/thing:929504",
    "description": "A fidget star that folds.",
    "license": "Creative Commons - Attribution - Non-Commercial - Share Alike",
    "allows_derivatives": True,
    "default_image": {"id": 1, "url": "https://cdn.thingiverse.com/default.jpg", "sizes": []},
    "images": [{"id": 1, "url": "https://cdn.thingiverse.com/img1.jpg"}],
    "download_count": 88583,
    "like_count": 8194,
    "collect_count": 10201,
    "added": "2015-07-17T03:09:52+00:00",
    "tags": [{"name": "fidget"}],
    "zip_data": {"files": [
        {"name": "mathgrrl_fidgetstar.scad",
         "url": "https://cdn.thingiverse.com/assets/mathgrrl_fidgetstar.scad"},
        {"name": "fidget_snub_standing_15_48.stl",
         "url": "https://cdn.thingiverse.com/assets/fidget_snub_standing_15_48.stl"},
    ], "images": []},
}

THINGIVERSE_FILES = [{
    "id": 1468104,
    "name": "mathgrrl_fidgetstar.scad",
    "size": 13547,
    "public_url": "https://www.thingiverse.com/download:1468104",
    "download_url": "https://api.thingiverse.com/v2/files/1468104/download",
    "direct_url": None,
}]
