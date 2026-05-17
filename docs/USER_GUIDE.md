# User Guide

This guide explains the main workflows in Finance Tracker once the backend and
frontend are running.

## 1. Start With Demo Data

The quick-start command in the root README creates a synthetic demo database.
Use it to explore the app without adding real financial data.

Open the app at `http://127.0.0.1:3000`.

## 2. Create Members and Accounts

Go to `Comptes`.

Use `+ Compte` to create accounts dynamically:

- name: display name shown in dashboards;
- type: current account, savings, investment, real estate, credit, or other;
- bank / institution: optional free text;
- currency: defaults to `EUR`;
- initial balance: first known balance;
- tracking start date: date from which you want to track the account;
- holders: select existing members or create a new holder inline.

Accounts are not hard-coded. A fresh install can be configured from the UI.

## 3. Import Transactions

Go to `Import`.

Typical workflow:

1. Choose the target account.
2. Upload a CSV or Excel bank export.
3. The backend normalizes dates, labels, amounts and debit/credit direction.
4. Duplicate rows are skipped using an import hash.
5. Transactions are pre-categorized with rules when possible.

Imported data stays in your local SQLite database. Do not commit that database.

## 4. Categorize Transactions

Go to `Transactions`.

You can:

- filter by month;
- filter uncategorized transactions;
- sort by date or amount;
- assign a category to one transaction;
- save a rule so similar transactions are categorized retroactively;
- mark a transaction as internal transfer, investment, neutral flow, or special
  income adjustment.

Internal transfers and neutral flows are excluded from budget calculations.

## 5. Review Budget and Dashboard

Go to `Budget` and the home dashboard.

The app summarizes:

- monthly income;
- monthly expenses;
- savings capacity;
- expenses by category group;
- rolling history and projections.

Projection behavior can be adjusted in `Paramètres`.

## 6. Track Net Worth

Go to `Patrimoine` and `Comptes`.

You can maintain monthly account snapshots:

- create a draft month;
- update account values;
- publish the month;
- compare assets, liabilities and net worth over time.

Credit accounts should use negative balances. Real estate or other assets should
use positive balances.

## 7. Simulator

Go to `Simulateur`.

The simulator uses current account balances and configurable assumptions to
estimate investment milestones. It is a planning helper, not financial advice.

## 8. Account Collector Agent

The account collector is optional. It produces JSON snapshots from demo fixtures,
manual files, or provider adapters. Finance Tracker can stage these snapshots
before importing them.

See `docs/AGENT_TECHNICAL.md` for the technical workflow.

## 9. Private Data Checklist

Before committing changes:

- never commit `.db`, `.sqlite`, `.env`, exports, backups or generated snapshots;
- keep provider tokens in ignored secret files;
- keep real account mappings in ignored private config files;
- use demo fixtures for screenshots, tests and public issues.
