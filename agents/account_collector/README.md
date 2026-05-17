# Account Collector Agent

Agent indépendant de collecte read-only des comptes financiers.

Phase 1 :
- lit une source `manual_file` JSON ;
- valide et normalise les comptes, soldes et transactions ;
- écrit un snapshot JSON horodaté ;
- fournit un CLI `collect` et `validate`.

Exemples :

```bash
cd agents/account_collector
python -m account_collector collect \
  --provider manual_file \
  --input fixtures/manual_sample.json \
  --output snapshots/latest.json

python -m account_collector validate snapshots/latest.json
```

Simulation du futur provider open banking :

```bash
python -m account_collector collect \
  --provider open_banking_fake \
  --config config/accounts.example.json \
  --output snapshots/open_banking_fake.json
```

Simulation d'un payload agrégateur HTTP :

```bash
python -m account_collector collect \
  --provider aggregator_mock \
  --config config/accounts.example.json \
  --fixture fixtures/aggregator_mock_accounts.json \
  --output snapshots/aggregator_mock.json
```

Simulation d'un payload Powens :

```bash
python -m account_collector collect \
  --provider powens_fixture \
  --config config/accounts.example.json \
  --fixture fixtures/powens_accounts_transactions.json \
  --output snapshots/powens_fixture.json
```

Provider Powens réel :

```bash
cp .env.example .env
# Fill .env with your local Powens values. Do not commit it.

python -m account_collector --env-file .env init-user \
  --provider powens \
  --output secrets/powens_user.json

# Copy auth_token from secrets/powens_user.json into AGGREGATOR_ACCESS_TOKEN in .env.

python -m account_collector --env-file .env create-webview-url \
  --provider powens \
  --redirect-uri http://localhost:3000/powens/callback \
  --output secrets/powens_connect_url.txt

# Open the generated URL in a browser and complete the bank consent flow.

python -m account_collector --env-file .env discover-accounts \
  --provider powens \
  --output snapshots/powens_accounts_raw.json

python -m account_collector --env-file .env collect \
  --provider powens \
  --config config/accounts.powens.json \
  --date-from 2026-01-01 \
  --date-to 2026-05-13 \
  --output snapshots/powens_real.json
```

Pour le provider réel, les `external_id` du fichier de config doivent correspondre
aux IDs de comptes renvoyés par Powens, sauf ajout ultérieur d'une table de mapping.

Le format de snapshot est volontairement indépendant de l'application `finance-tracker`.
L'agent ne doit pas écrire directement dans la base principale. Les snapshots
produits sont relus par `finance-tracker` en staging, puis validés depuis
l'application avant intégration.
