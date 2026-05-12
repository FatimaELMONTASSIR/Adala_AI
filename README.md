# LexMaroc

**LexMaroc** est une application d'assistance juridique spécialisée dans le droit marocain (français uniquement), basée sur une architecture **RAG** (génération augmentée par récupération) et le modèle **Claude** d'Anthropic. Les textes sont indexés dans **MongoDB Atlas** et **Qdrant Cloud** ; l'interface est développée avec **Streamlit**.

## Architecture (schéma ASCII)

```
┌─────────────┐     PDF / data      ┌──────────────────┐
│   Dossier   │ ──────────────────► │   Ingestion      │
│   data/*.pdf│                     │ pdf_extractor +  │
└─────────────┘                     │ chunker          │
                                    └────────┬─────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
            ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
            │ sentence-     │        │ MongoDB Atlas │        │ Qdrant Cloud  │
            │ transformers  │        │ (métadonnées) │        │ (vecteurs 384)│
            └───────┬───────┘        └───────────────┘        └───────┬───────┘
                    │                                                  │
                    └──────────────────────┬───────────────────────────┘
                                           │
                                           ▼
                                  ┌────────────────┐
                                  │  Streamlit UI  │
                                  │  app.py        │
                                  └────────┬───────┘
                                           │
              Question utilisateur ────────┼──────── RAG (retrieve + prompt)
                                           ▼
                                  ┌────────────────┐
                                  │ Anthropic API  │
                                  │ Claude Sonnet  │
                                  └────────────────┘
```

## Prérequis

1. **Python 3.11 ou supérieur**
2. Compte **Anthropic** avec clé API (`ANTHROPIC_API_KEY`)
3. Cluster **MongoDB Atlas** (gratuit M0) et chaîne de connexion `mongodb+srv://...`
4. Instance **Qdrant Cloud** (gratuit) : URL (`https://....qdrant.io`) et clé API
5. Fichiers **PDF** des codes à indexer (par défaut dans `lexmaroc/data/`, ou un autre dossier via `LEXMAROC_DATA_DIR`, voir ci-dessous)

## Installation pas à pas

1. Cloner ou copier le dossier `lexmaroc/` sur votre machine.

2. Créer un environnement virtuel (recommandé) :

   ```bash
   python -m venv .venv
   ```

   Sous Windows PowerShell :

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Installer les dépendances :

   ```bash
   cd lexmaroc
   pip install -r requirements.txt
   ```

4. Configurer les variables d'environnement :

   - Copier le fichier `env.example.txt` vers un fichier nommé `.env` **à la racine du dossier `lexmaroc/`** (fichier local non versionné).
   - Renseigner les clés et URL réelles (MongoDB, Qdrant, Anthropic).

   Sous **Streamlit Cloud**, utiliser l'écran **Secrets** et reprendre exactement les mêmes noms de clés que dans `env.example.txt` (voir section déploiement).

## Dossier des PDF (`LEXMAROC_DATA_DIR`)

Par défaut, l’ingestion lit les fichiers `*.pdf` dans **`lexmaroc/data/`**.

Si vous avez déplacé les PDF ailleurs, définissez **`LEXMAROC_DATA_DIR`** dans `.env` ou dans l’environnement :

- **Chemin absolu** (recommandé si le dossier est en dehors du projet) :  
  `LEXMAROC_DATA_DIR=/chemin/vers/mes_pdfs`
- **Chemin relatif** à la racine `lexmaroc/` :  
  `LEXMAROC_DATA_DIR=../donnees_juridiques`  
  ou `LEXMAROC_DATA_DIR=documents/codes`

Sous **Streamlit Cloud**, ajoutez la même clé dans les secrets si l’ingestion s’exécute dans un job qui charge ce fichier d’environnement ; l’application chat n’a pas besoin de cette variable pour fonctionner une fois l’index construit.

## Lancer l'ingestion des PDF

Depuis le répertoire **`lexmaroc/`** (celui qui contient `app.py` et le dossier `backend/`) :

```bash
python -m backend.ingestion.ingest
```

Le script :

1. lit tous les `*.pdf` dans le dossier configuré (`data/` par défaut, ou `LEXMAROC_DATA_DIR`)
2. découpe le texte en articles (marqueurs du type « Article », « Art. », « ARTICLE », « Article premier »)
3. calcule les embeddings
4. écrit dans MongoDB (collection `articles`) et dans Qdrant (collection `lexmaroc_articles` par défaut)
5. affiche un résumé dans la console

Si aucun PDF n'est présent ou si aucun article n'est détecté, un message explicite s'affiche.

## Lancer l'application en local

Toujours depuis `lexmaroc/` :

```bash
streamlit run app.py
```

Le navigateur s'ouvre sur l'interface de chat. Vérifiez que le fichier `.env` est bien présent ou que les variables sont exportées dans l'environnement du terminal.

## Déploiement sur Streamlit Cloud

1. Héberger le dépôt contenant le dossier `lexmaroc/` sur GitHub (ou autre forge supportée).

2. Dans Streamlit Cloud, créer une application dont le **répertoire racine** est **`lexmaroc`** et le **fichier principal** est **`app.py`**.

3. Ouvrir **Settings → Secrets** et coller un bloc TOML du type :

   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
   MAX_TOKENS = "1000"
   MONGO_URI = "mongodb+srv://..."
   MONGO_DB_NAME = "lexmaroc"
   QDRANT_URL = "https://....qdrant.io"
   QDRANT_API_KEY = "..."
   QDRANT_COLLECTION = "lexmaroc_articles"
   TOP_K_RESULTS = "5"
   EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
   ```

   L'application copie automatiquement ces secrets dans `os.environ` au démarrage si les variables ne sont pas déjà définies.

4. **Premier chargement** : le modèle d'embeddings `sentence-transformers` est téléchargé et mis en cache ; le premier démarrage peut être long.

5. L'ingestion (`python -m backend.ingestion.ingest`) doit être exécutée **une fois** depuis une machine disposant des PDF et des accès réseau (CI locale, machine de développement ou job planifié), car Streamlit Cloud ne contient en général pas vos PDF sources dans le dépôt public.

## Dépannage

| Problème | Piste de résolution |
|----------|---------------------|
| `MONGO_URI` manquant ou refus de connexion | Vérifier l'URI Atlas, l'utilisateur, le mot de passe et l'IP autorisée (**Network Access** : `0.0.0.0/0` pour les tests). |
| Erreur Qdrant (401, 403) | Contrôler `QDRANT_URL` et `QDRANT_API_KEY` ; vérifier que la collection existe ou laisser le script la créer. |
| Erreur Anthropic | Vérifier `ANTHROPIC_API_KEY` et le quota du compte. |
| Aucun article après ingestion | Les PDF doivent contenir des titres d'articles reconnus par le découpeur ; voir `data/README_data.txt`. Vérifiez aussi `LEXMAROC_DATA_DIR` si vous n'utilisez pas `data/`. |
| `ModuleNotFoundError` | S'assurer d'avoir activé le bon environnement virtuel et relancé `pip install -r requirements.txt`. |
| Déploiement Streamlit très lent au premier message | Normal : chargement de PyTorch et du modèle d'embeddings ; les requêtes suivantes sont plus rapides. |
| Réponses hors sujet ou sans citation | Vérifier que l'ingestion a bien peuplé Qdrant ; contrôler les logs d'erreur dans l'interface Streamlit. |

## Licence et avertissement

LexMaroc fournit des **informations à titre indicatif** extraites des textes indexés. Il **ne remplace pas** l'analyse d'un avocat ou d'un professionnel du droit habilité au Maroc.
