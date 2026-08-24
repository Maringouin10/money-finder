# money-finder

Scraper multi-plateformes de modèles 3D **vendables**. Il interroge
**MakerWorld**, **Creality Cloud**, **Printables** et **Thingiverse** (API
officielle), analyse la **licence** de chaque modèle pour dire si tu as le droit
de vendre les impressions, et produit un compte rendu HTML en 2 pages :

| Page | Contenu |
|---|---|
| `index.html` | **Tous les modèles** : image, nom, description, licence + verdict commercial, fichiers 3D, auteur, stats. Filtres par licence / plateforme / famille, recherche, tri. |
| `groupes.html` | **Regroupés par famille** (Infinity Cube, Planetary Gear, Fidget Slider…), familles **découvertes automatiquement** à partir des titres — aucune liste écrite en dur. |

Exports bruts également générés : `models.json` et `models.csv` (ouvrable dans Excel).

---

## Démarrage rapide (Docker)

```bash
cp .env.example .env      # puis colle ton token Thingiverse dedans
docker compose build
docker compose run --rm scraper                 # lance la collecte
docker compose up -d web                        # rapport sur http://localhost:8080
```

Le rapport atterrit dans `./output/` (monté en volume, donc conservé entre les runs).

### Voir le rendu sans clé ni réseau

```bash
docker compose run --rm scraper --demo
```

Génère un rapport d'exemple avec des fiches fictives : utile pour vérifier la
mise en page et le regroupement automatique.

---

## Utilisation

Tous les réglages ont une valeur par défaut dans `.env`, surchargeable en ligne
de commande :

```bash
# autres mots-clés, 100 résultats par mot-clé et par plateforme
docker compose run --rm scraper -k "infinity cube,planetary gear,fidget slider" -l 100

# uniquement Printables + MakerWorld, et seulement le vendable (licences douteuses exclues)
docker compose run --rm scraper -s printables,makerworld --commercial-only --strict

# familles plus petites (2 modèles suffisent pour créer un dossier)
docker compose run --rm scraper --min-group-size 2
```

| Option | Effet |
|---|---|
| `-k, --keywords` | mots-clés séparés par des virgules |
| `-s, --sources` | `thingiverse,printables,makerworld,crealitycloud` |
| `-l, --limit` | nombre de modèles par mot-clé **et** par plateforme |
| `-o, --output` | dossier de sortie (défaut `output`) |
| `--commercial-only` | ne garde que ce qui est exploitable commercialement |
| `--strict` | avec `--commercial-only`, exclut aussi les licences non identifiées |
| `--min-group-size` | taille minimale d'une famille (défaut 3) |
| `--no-images` | ne pas télécharger les vignettes (rapport plus léger, images distantes) |
| `--no-enrich` | ne pas ouvrir les pages détail : beaucoup plus rapide, mais licences, descriptions et fichiers incomplets (voir ci-dessous) |
| `--demo` | rapport d'exemple hors-ligne |
| `-v, --verbose` | journal détaillé |

Sans Docker : `pip install -r requirements.txt && python -m scraper --demo`.

---

## Enrichissement : à laisser activé

La recherche seule ne suffit pas sur trois plateformes :

| Plateforme | Manque dans les résultats de recherche |
|---|---|
| Thingiverse | **licence**, description, nombre de téléchargements |
| MakerWorld | description, liste des fichiers |
| Creality Cloud | description, tags, liste des fichiers |

`ENRICH_DETAILS=true` (défaut) ouvre la page détail de chaque modèle pour les
récupérer. Avec `--no-enrich`, tous les modèles Thingiverse ressortiraient
« licence à vérifier » — un avertissement est affiché en haut du rapport dans ce
cas.

## Clés d'API

Seul **Thingiverse** exige une clé : crée une app sur
<https://www.thingiverse.com/apps/create>, récupère l'**App Token** et mets-le
dans `.env` :

```
THINGIVERSE_TOKEN=xxxxxxxxxxxxxxxx
```

Les trois autres plateformes sont interrogées via leurs API web publiques, sans
compte. `.env` n'est jamais commité (`.gitignore`).

---

## Analyse des licences

Chaque licence brute est ramenée à un code canonique, puis classée :

| Verdict | Signification | Exemples |
|---|---|---|
| 🟢 **Vendable** | vente des impressions autorisée (crédit auteur si BY) | CC0, CC-BY, MIT, BSD |
| 🟠 **Vendable sous conditions** | autorisé mais avec contrainte forte | CC-BY-SA (repartage identique), CC-BY-ND (aucune modification), GPL |
| 🔴 **Vente interdite** | clause non-commerciale ou licence propriétaire | CC-BY-NC*, Standard Digital File License, BSDL, tous droits réservés |
| ⚪ **À vérifier** | licence absente ou non reconnue | champ vide côté plateforme |

Chaque fiche affiche le verdict, le code, la licence **brute** renvoyée par la
plateforme et une note expliquant l'obligation (crédit, partage à l'identique…).

> Ce classement est une aide à la décision automatisée, pas un avis juridique :
> avant de vendre, ouvre la page du modèle et vérifie la licence affichée par
> l'auteur (certains ajoutent des conditions dans la description).

---

## Regroupement automatique

`scraper/grouping.py` extrait des titres les expressions de 1 à 3 mots après
retrait des mots trop génériques (`fidget`, `toy`, `print in place`, `v2`,
`multicolor`…), garde celles qui reviennent au moins `MIN_GROUP_SIZE` fois, et
attribue à chaque modèle l'expression la plus **précise** qui le décrit —
« Infinity Cube » l'emporte sur « Cube ». Les singuliers/pluriels sont fusionnés,
les modèles isolés tombent dans « Divers ». Les familles changent donc toutes
seules selon ce qui est trouvé : rien n'est codé en dur.

Les modèles publiés sous le même titre sur plusieurs plateformes sont signalés
(« aussi sur MakerWorld, Printables »).

---

## Architecture

```
scraper/
  __main__.py      CLI
  config.py        .env + arguments
  pipeline.py      collecte -> enrichissement -> filtre -> regroupement -> rapport
  http.py          client HTTP (retries, backoff, throttling)
  licenses.py      normalisation des licences + verdict commercial
  grouping.py      découverte automatique des familles
  report.py        rendu HTML/JSON/CSV
  models.py        structures communes
  demo_data.py     jeu d'exemple hors-ligne
  sources/
    base.py            contrat commun + lecture JSON tolérante
    nuxt.py            décodage des payloads Nuxt/devalue (Creality Cloud)
    thingiverse.py     API officielle (token)
    printables.py      GraphQL searchPrints2 / print(id)
    makerworld.py      API web publique (select/design2)
    crealitycloud.py   POST smart_search + page détail rendue côté serveur
templates/         pages Jinja2 + CSS/JS du rapport
tests/             tests unitaires + échantillons d'API réels
docs/              apis.md (référence des endpoints), prompt-sonde-api.md
```

### Robustesse

Les endpoints ont été relevés en conditions réelles (voir **`docs/apis.md`** :
URLs, chemins des résultats, correspondance champ par champ, pièges connus).
Comme ces API ne sont pas documentées et changent, les connecteurs :

- lisent d'abord le chemin validé (`records_at`), puis retombent sur une
  recherche heuristique dans la réponse (`first_records`) ;
- résolvent les champs via `pick()`, qui accepte plusieurs noms possibles ;
- décodent le payload Nuxt *devalue* de Creality Cloud (`sources/nuxt.py`),
  seule voie d'accès au détail en anonyme ;
- n'interrompent jamais le run : une plateforme en panne produit un
  **avertissement affiché en haut du rapport**, les autres continuent.

Des échantillons de réponses réelles sont figés dans `tests/fixtures.py` et
rejoués par `tests/test_sources.py` : un changement de forme d'API casse les
tests avant de fausser un rapport.

Si une plateforme ne renvoie plus rien, lance
`docker compose run --rm scraper -v -s makerworld -l 5` pour voir les erreurs,
puis ajuste l'endpoint dans `.env` (voir les variables commentées dans
`.env.example`). Le fichier `docs/prompt-sonde-api.md` contient un prompt prêt à
l'emploi pour redécouvrir la forme exacte des API, et `docs/apis.md` sert de
référence de ce qui a été validé la dernière fois.

---

## Tests

```bash
python -m unittest discover -s tests -t .
```

27 tests : normalisation des licences (y compris les codes nus `BY-SA` de
MakerWorld et `CXY-SL` de Creality), découverte des familles, lecture tolérante
des réponses JSON, décodage devalue et mapping de chaque plateforme sur des
échantillons de réponses réelles.

---

## Notes d'usage

Le scraping n'est fait que sur des pages/API publiques, à raison d'une requête
toutes les 0,8 s par défaut (`REQUEST_DELAY`). Reste raisonnable sur les volumes,
et respecte les conditions d'utilisation de chaque plateforme.
