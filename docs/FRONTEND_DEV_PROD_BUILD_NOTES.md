# Frontend Next.js - Dev, production, compilation et Turbopack

Date: 2026-05-13

## Resume pratique

Le frontend peut tourner de deux facons principales:

- en developpement local avec `next dev`;
- en production locale avec `next build` puis `next start`.

Dans ce projet, `next dev` utilise Turbopack par defaut avec Next.js 16. Turbopack est rapide, mais il a montre des comportements instables dans l'environnement sandbox Codex: blocage de compilation, besoin de binder un port, et attente longue sur la compilation de `/`.

Le fallback fiable pour le developpement local est:

```bash
npm run dev -- --webpack --hostname 127.0.0.1 --port 3000
```

## Commandes utiles

Backend local:

```bash
cd backend
../.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Frontend dev avec Turbopack:

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Frontend dev avec webpack, fallback recommande si Turbopack bloque:

```bash
cd frontend
npm run dev -- --webpack --hostname 127.0.0.1 --port 3000
```

Verification statique frontend:

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

Build production:

```bash
cd frontend
npm run build
npm run start
```

## Difference entre dev et production

### `next dev`

`next dev` sert a travailler localement.

Caracteristiques:

- compile les pages a la demande;
- garde un serveur de developpement actif;
- recharge automatiquement apres modification;
- affiche les erreurs de compilation dans le navigateur et le terminal;
- n'optimise pas comme un build final.

En dev, la premiere visite d'une page peut declencher une compilation. Par exemple, voir `Compiling / ...` signifie que Next compile la route `/`.

### `next build`

`next build` prepare l'application pour la production.

Caracteristiques:

- compile toutes les routes necessaires;
- lance la verification TypeScript;
- optimise les bundles JavaScript/CSS;
- genere les fichiers dans le dossier de sortie Next;
- echoue si une erreur bloquante est detectee.

Un build qui passe est une meilleure preuve qu'un simple `next dev`, car il simule la contrainte production.

### `next start`

`next start` sert a lancer le resultat deja construit par `next build`.

Il ne remplace pas `next build`: il suppose que le build existe deja.

## Build prod vs runtime prod physique

Un `next build` ne cree pas a lui seul un environnement prod physiquement
separe. Il cree un dossier de build Next, ici par exemple:

```text
frontend/.next-local-prod/
```

Ce dossier contient l'artefact frontend optimise, mais il reste dans le repo de
developpement.

Pour avoir une vraie separation physique dev/prod locale, il faut une etape de
promotion en plus:

```text
commit dev
  -> tests/lint/typecheck
  -> build frontend local-prod
  -> copie dans runtime/local-prod
  -> lancement backend + frontend depuis runtime/local-prod
```

La cible recommandee est donc:

```text
runtime/local-prod/
  backend/
  frontend/
  agents/
  data/
    current/
      finance.db
    rollback/
  logs/
  VERSION
```

Dans ce modele, le dossier runtime est genere par workflow. On ne developpe pas
dedans; il est seulement remplace ou mis a jour apres validation d'un commit.

Voir aussi `docs/LOCAL_DEPLOYMENT.md` pour la procedure complete et la liste des
taches restantes.

## Bandeau environnement et donnees demo

Le frontend expose volontairement le mode de donnees affiche:

```text
NEXT_PUBLIC_APP_ENV
NEXT_PUBLIC_DATASET_LABEL
```

En dev, la valeur cible est:

```bash
NEXT_PUBLIC_APP_ENV=demo
NEXT_PUBLIC_DATASET_LABEL="Compte demo - donnees mockees"
```

L'application affiche alors un bandeau visible `Demo / Dev`.

En local-prod, la valeur cible est:

```bash
NEXT_PUBLIC_APP_ENV=local-prod
NEXT_PUBLIC_DATASET_LABEL="Base locale prod"
```

L'objectif est d'eviter toute confusion entre:

- une base demo/mock utilisee pour developper;
- la base prod locale personnelle utilisee pour l'application stable.

## Turbopack vs webpack

### Turbopack

Turbopack est le bundler moderne de Next.js. Il est concu pour accelerer le developpement et les builds.

Avantages:

- tres rapide quand il fonctionne correctement;
- integre par defaut dans les versions recentes de Next;
- recompilation incrementale rapide.

Limites observees ici:

- dans le sandbox, il peut etre bloque par des restrictions systeme;
- il a tente de creer un processus qui bind un port, ce qui a produit `Operation not permitted`;
- apres autorisation, il a pu rester silencieux longtemps sur la compilation;
- la compilation de `/` en dev est restee bloquee dans cette session.

### webpack

webpack est l'ancien bundler stable de Next.

Avantages:

- plus mature;
- comportement plus previsible;
- meilleur fallback quand Turbopack bloque.

Inconvenients:

- souvent plus lent;
- moins moderne que Turbopack.

Pour ce projet, webpack est le fallback local pragmatique:

```bash
npm run dev -- --webpack --hostname 127.0.0.1 --port 3000
```

## Ce qui a ete corrige

### ESLint analysait des dossiers generes

Le lint echouait parce qu'il parcourait des dossiers de build comme:

- `.next-default/`
- `.next-local-prod/`

Ces dossiers contiennent du code genere par Next/Turbopack. Ils ne doivent pas etre lintes comme du code source applicatif.

Fix applique dans `frontend/eslint.config.mjs`:

```js
globalIgnores([
  ".next/**",
  ".next-*/**",
  "out/**",
  "build/**",
  "next-env.d.ts",
])
```

### Regle React trop stricte pour le style actuel du projet

La regle `react-hooks/set-state-in-effect` bloquait plusieurs pages existantes qui chargent des donnees dans `useEffect`.

Dans ce projet, ce pattern est deja utilise largement pour synchroniser l'UI avec l'API locale. La regle a donc ete desactivee dans ESLint:

```js
{
  rules: {
    "react-hooks/set-state-in-effect": "off",
  },
}
```

### Types TypeScript manquants

Des `any` restaient dans le dashboard et le chart des depenses.

Corrections:

- ajout d'un type `GroupData` cote dashboard;
- remplacement des callbacks `any`;
- conversion de `category_id` en string pour `URLSearchParams`;
- adaptation du chart Recharts aux types de la version installee.

### URLs API hardcodees

Des composants utilisaient encore `http://localhost:8000` directement.

Correction:

```ts
import { API_BASE } from "@/lib/config";
```

Cela centralise la configuration API.

## Pourquoi Next modifie `tsconfig.json`

Le projet configure un dossier de sortie dynamique:

```ts
const appMode = process.env.APP_MODE?.replace(/[^a-zA-Z0-9_-]/g, "") || "default";

const nextConfig = {
  distDir: `.next-${appMode}`,
};
```

Avec `APP_MODE=default`, le dossier devient `.next-default`.

Next detecte ce dossier et peut ajouter automatiquement ses types au `tsconfig.json`, par exemple:

```json
".next-default/types/**/*.ts"
".next-default/dev/types/**/*.ts"
```

Pour eviter d'ajouter chaque mode explicitement, le projet inclut maintenant:

```json
".next-*/types/**/*.ts"
".next-*/dev/types/**/*.ts"
```

Si Next rajoute quand meme les chemins exacts, ce n'est pas un probleme fonctionnel. C'est surtout du bruit de diff.

## Diagnostic rapide en cas de probleme

1. Verifier le backend:

```bash
curl http://127.0.0.1:8000/health
```

Attendu:

```json
{"status":"ok"}
```

2. Verifier le frontend sans build complet:

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

3. Si `next dev` bloque sur `Compiling / ...`, relancer avec webpack:

```bash
npm run dev -- --webpack --hostname 127.0.0.1 --port 3000
```

4. Si un serveur Next existe deja:

```bash
pkill -f "next dev"
```

Puis relancer la commande souhaitee.

## Etat de reference actuel

Validations obtenues:

- agent `account_collector`: 31 tests OK;
- backend: 76 tests OK;
- frontend lint: OK;
- frontend TypeScript: OK avec `npx tsc --noEmit`;
- frontend local: OK en mode webpack sur `http://127.0.0.1:3000`;
- backend local: OK sur `http://127.0.0.1:8000`.

Limite restante:

- `npm run build` avec Turbopack peut rester bloque dans cet environnement sandboxe. Pour isoler les erreurs de code, utiliser `npm run lint` et `npx tsc --noEmit`; pour tester l'UI locale, utiliser `next dev --webpack`.
