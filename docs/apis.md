# APIs des plateformes — référence

Relevé de sonde du **2026-08-23** (voir `docs/prompt-sonde-api.md` pour refaire
le test). Ces APIs ne sont pas documentées publiquement et changent : si une
source ne renvoie plus rien, c'est ici qu'il faut revenir.

## Endpoints validés

| Plateforme | Méthode | URL | Auth | Résultats |
|---|---|---|---|---|
| MakerWorld — recherche | `GET` | `/api/v1/search-service/select/design2?keyword=…&limit=…&offset=…` | aucune | `hits[]` |
| MakerWorld — détail | `GET` | `/api/v1/design-service/design/{id}` | aucune | racine |
| Printables — recherche | `POST` | `https://api.printables.com/graphql/` — `searchPrints2` | aucune | `data.result.items[]` |
| Printables — détail | `POST` | idem — `print(id: ID!)` | aucune | `data.print` |
| Creality — recherche | `POST` | `https://www.crealitycloud.com/api/cxy/smart_search/v1/model` | aucune | `result.list[]` |
| Creality — détail | `GET` | `https://www.crealitycloud.com/model-detail/{id}` (HTML) | aucune | `__NUXT_DATA__` (devalue) |
| Thingiverse — recherche | `GET` | `https://api.thingiverse.com/search/{kw}/?type=things&per_page=…` | **Bearer** | `hits[]` |
| Thingiverse — détail | `GET` | `https://api.thingiverse.com/things/{id}` | Bearer | racine |
| Thingiverse — fichiers | `GET` | `https://api.thingiverse.com/things/{id}/files` | Bearer | tableau racine |

## Pièges rencontrés

**MakerWorld**
- `select/design` (sans le `2`) répond `200` mais avec `total: 0` : index mort.
- Pagination par **`offset`**, pas `page`. `sort=hot` n'existe pas (`orderBy=score`).
- Le hit de recherche n'a **aucune description** → `enrich()` obligatoire pour `summary`.
- Fichiers dans `designExtension.model_files[]` (`modelName`, `modelSize`, `modelUrl`),
  avec dossiers (`isDir` + `children`) à aplatir. `instances[]` = profils
  d'impression, sans nom de fichier : inutilisables comme fichiers.
- `modelUrl` est vide en anonyme → on renvoie la page du modèle.

**Printables**
- Introspection désactivée ; `searchPrints` (sans `2`) n'existe plus.
- **Pas de curseur** : `ListPrintType` n'expose que `items` et `totalCount` → pagination `offset`.
- Les enums doivent être des **littéraux non quotés** : `printType: print`, `ordering: best_match`.
- `filePath` n'existe **pas** sur `STLType`/`SLAType`/`OtherFileType`/`GCodeType` :
  le demander fait échouer toute la requête de détail. Aucune URL de fichier
  n'est exposée → lien vers l'onglet `/files` du modèle.
- `user.publicUsername` est le **nom affiché** ; l'URL de profil utilise `user.handle`.
- `license.abbreviation` est plus propre que `license.name` (tirets cadratins).

**Creality Cloud**
- Host `api-cxy.crealitycloud.com` : mort. Tout passe par `www.crealitycloud.com`.
- Recherche en **POST JSON** ; les clés `key`/`query` sont ignorées, c'est `keyword`.
- `code: 0` = succès, `code: 1` = `Invalid Parameter`.
- Site en **Nuxt 3** : le payload est dans `<script id="__NUXT_DATA__">` au format
  *devalue* (tableau plat, les entiers sont des index) → résolveur dans
  `scraper/sources/nuxt.py`. Aucune regex `__NEXT_DATA__`/`__NUXT__` ne marche.
- `modelGroupDetail` refuse les appels anonymes → détail lu depuis la page HTML.
- Champs : titre = `groupName`, description = `groupDesc`, image = `covers[0].url`,
  auteur = `userInfo.nickName`, date = `createTime` **epoch en secondes**.
- Le paramètre `licenses` du POST permettrait un filtrage licence côté serveur.

**Thingiverse**
- Sans token : `401`. Le hit de recherche n'a **ni `license`, ni `description`,
  ni `download_count`** → `ENRICH_DETAILS=true` est indispensable, sinon toutes
  les licences ressortent « à vérifier ».
- `collect_count` (collections) ≠ `download_count` : ne jamais l'utiliser comme substitut.
- Date : `created_at` dans la recherche, `added` dans le détail.
- Pas de champ `zip_url` ; les URLs CDN directes sont dans `zip_data.files[].url`.
- Fichiers : `public_url` = page publique (OK dans le rapport),
  `download_url` = API authentifiée, `direct_url` = toujours `null`.

## Valeurs de licence observées

| Plateforme | Valeurs brutes |
|---|---|
| MakerWorld | `Standard Digital File License` (majoritaire), `BY`, `BY-SA`, `BY-NC`, `BY-ND`, `BY-NC-SA`, `BY-NC-ND`, `MakerWorld Exclusive License` |
| Printables | `CC-BY`, `CC-BY-SA`, `CC-BY-NC`, `CC-BY-NC-SA`, `CC-BY-NC-ND`, `CC0`, `GPL 3.0`, `Standard Digital File` |
| Creality Cloud | `CXY-SL` (majoritaire, = licence maison), `CC BY-SA`, `CC BY-NC-SA`, `CC BY-NC-ND`, vide |
| Thingiverse | libellés longs `Creative Commons - Attribution - …`, `Creative Commons - Public Domain Dedication` |

Toutes ces valeurs sont couvertes par `scraper/licenses.py` (tests dans
`tests/test_licenses.py`). Les échantillons de réponses réelles sont figés dans
`tests/fixtures.py` : si une API change de forme, `tests/test_sources.py` casse
avant le scraping.
