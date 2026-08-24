# Prompt de sondage des API (à lancer sur ta machine)

Copie-colle le bloc ci-dessous dans Claude Code **sur ton PC** (réseau ouvert),
depuis le dossier du projet. Il ne modifie aucun code : il écrit seulement un
rapport `sonde-resultats.md` que tu peux me renvoyer.

> ⚠️ Le prompt demande explicitement de **masquer le token Thingiverse** dans le
> rapport. Relis quand même le fichier avant de me l'envoyer.

---

```
Tu es en mode diagnostic réseau, tu ne modifies AUCUN fichier du projet sauf `sonde-resultats.md`.

Objectif : découvrir la forme réelle des API publiques de MakerWorld, Printables,
Creality Cloud et Thingiverse, pour fiabiliser les connecteurs du projet money-finder.

Règles :
- N'écris jamais de clé/token dans le rapport : remplace-les par <REDACTED>.
- Tronque chaque extrait JSON à ~40 lignes, mais garde TOUS les noms de champs.
- Si une requête échoue, note le code HTTP et le début du corps de réponse.
- 1 requête par seconde maximum, user-agent de navigateur.

Étapes :

1) MakerWorld
   curl "https://makerworld.com/api/v1/search-service/select/design?keyword=fidget&page=1&limit=3"
   Puis, avec le premier id trouvé :
   curl "https://makerworld.com/api/v1/design-service/design/<ID>"
   Rapporte : code HTTP, chemin exact de la liste de résultats dans le JSON
   (ex. data.hits[]), la liste complète des clés d'un résultat, et surtout le nom
   ET la valeur du champ de licence, du champ image/cover, du champ auteur, du
   champ nombre de téléchargements, et la structure des fichiers/instances.
   Si un header est nécessaire (403/401), trouve lequel et note-le.

2) Printables (GraphQL, https://api.printables.com/graphql/)
   Teste les 3 requêtes du fichier scraper/sources/printables.py (SEARCH_QUERIES)
   avec {"query":"fidget","limit":3,"cursor":null}, headers
   content-type: application/json, origin: https://www.printables.com.
   Indique laquelle passe. Pour celles qui échouent, copie le message d'erreur
   GraphQL (il nomme le champ correct). Si aucune ne passe, fais une
   introspection ciblée :
   {"query":"{__schema{queryType{fields{name args{name type{name kind ofType{name}}}}}}}"}
   et donne le nom exact de la query de recherche + ses arguments, puis les
   champs disponibles sur le type retourné (id, name, slug, license, image...).
   Récupère aussi la forme du détail d'un modèle (description, license, fichiers STL).

3) Creality Cloud
   Ouvre https://www.crealitycloud.com/search?keyword=fidget (curl du HTML) et
   cherche : un JSON embarqué (__NEXT_DATA__, __NUXT__, __INITIAL_STATE__) OU les
   appels XHR référencés dans les bundles JS. Objectif : l'URL exacte de l'API de
   recherche de modèles, ses paramètres, ses headers obligatoires, et la forme
   d'un résultat (id, nom, cover, licence, auteur). Teste l'URL trouvée avec curl
   et colle la réponse tronquée.

4) Thingiverse (si tu as un token dans .env, sinon saute)
   curl -H "Authorization: Bearer $THINGIVERSE_TOKEN" "https://api.thingiverse.com/search/fidget/?type=things&per_page=3"
   curl -H "Authorization: Bearer $THINGIVERSE_TOKEN" "https://api.thingiverse.com/things/<ID>"
   curl -H "Authorization: Bearer $THINGIVERSE_TOKEN" "https://api.thingiverse.com/things/<ID>/files"
   Confirme : nom du champ licence + valeurs possibles observées, champ image,
   champ auteur, champs de fichiers (download_url / public_url).

Écris tout dans `sonde-resultats.md`, une section par plateforme, avec pour
chacune : URL testée, code HTTP, headers requis, chemin des résultats, tableau
"champ money-finder -> champ réel", extraits JSON tronqués.
```

---

Renvoie-moi le contenu de `sonde-resultats.md` : j'ajuste les connecteurs
(`scraper/sources/*.py`) avec les vrais noms de champs.
