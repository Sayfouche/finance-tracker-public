"""
Migration one-shot depuis demo_patrimony_template.xlsx
Importe l'historique mensuel (jan 2025 → aujourd'hui) en PatrimonySnapshots.
"""
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from db.models import Account, PatrimonySnapshot


# Mapping feuille Excel → (nom_colonne, nom_compte_en_base)
SHEET_MAPPINGS = {
    "Courants": [
        ("Compte Demo A",    "Compte Demo A"),
        ("Compte Demo B", "CC Demo Bank B"),
        ("CC Revolut","CC Revolut"),
        ("Compte pro demo","Compte pro demo"),
    ],
    "Livrets": [
        ("Livret demo source", "Livret Demo A"),
        ("Livret Demo B", "Livret Demo B"),
        ("Livret Charlie",  "Livret Charlie"),
        ("C Bloqué",      "Compte Bloqué"),
        ("Livret Reserve A",      "Livret Reserve A"),
        ("Livret Reserve B",      "Livret Reserve B"),
    ],
    # CTO_PEA a un header multi-niveau — géré séparément dans migrate_cto_pea()
    # "CTO_PEA": [],
    "PER": [
        ("PER M-T Sam",  "PER Demo Assurance Sam"),
        ("PER source Alex",  "PER Demo Assurance Alex"),
        ("PER PYR Sam",  "PER Demo Retraite Sam"),
        ("PER retraite source Alex",  "PER Demo Retraite Alex"),
    ],
    "AV": [
        ("AV source Alex",   "AV Alex"),
        ("AV- M-T Sam",  "AV Sam"),
        ("AV Charlie",      "AV Charlie"),
        ("AV Jordan",      "AV Jordan"),
        ("AV Taylor",       "AV Taylor"),
    ],
}


TODAY = datetime.now().strftime("%Y-%m")


def _parse_month(date_val) -> str | None:
    """Convertit une valeur date Excel en format YYYY-MM. Rejette les dates futures."""
    if date_val is None:
        return None
    try:
        if isinstance(date_val, datetime):
            month = date_val.strftime("%Y-%m")
        elif isinstance(date_val, str):
            month = pd.to_datetime(date_val).strftime("%Y-%m")
        else:
            month = pd.Timestamp(date_val).strftime("%Y-%m")
        # Rejeter les projections futures
        return month if month <= TODAY else None
    except Exception:
        return None


def _get_account(db: Session, name: str) -> Account | None:
    return db.query(Account).filter(Account.name == name).first()


def migrate_sheet(db: Session, df: pd.DataFrame, col_account_pairs: list[tuple]) -> int:
    """
    Parcourt un DataFrame et crée des PatrimonySnapshots.
    col_account_pairs : [(col_excel, nom_compte_db), ...]
    Retourne le nombre de snapshots créés.
    """
    created = 0

    # La première colonne est toujours la date
    date_col = df.columns[0]

    for _, row in df.iterrows():
        month = _parse_month(row[date_col])
        if not month:
            continue

        for col_excel, account_name in col_account_pairs:
            if col_excel not in df.columns:
                continue

            value = row.get(col_excel)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            account = _get_account(db, account_name)
            if not account:
                continue

            # Éviter les doublons
            existing = db.query(PatrimonySnapshot).filter_by(
                account_id=account.id, month=month
            ).first()
            if existing:
                existing.value = value
            else:
                db.add(PatrimonySnapshot(
                    account_id=account.id,
                    month=month,
                    value=value,
                    note="Import Excel initial",
                ))
                created += 1

    return created


def migrate_pret_immo(db: Session, df: pd.DataFrame) -> int:
    """Importe le capital restant dû du prêt immo comme snapshots mensuels."""
    account = _get_account(db, "Prêt immo")
    if not account:
        return 0

    created = 0
    for _, row in df.iterrows():
        month = _parse_month(row.get("Échéance"))
        if not month:
            continue

        restant = row.get("Restant dû")
        if restant is None or (isinstance(restant, float) and pd.isna(restant)):
            continue

        try:
            value = -abs(float(restant))  # passif → négatif
        except (ValueError, TypeError):
            continue

        existing = db.query(PatrimonySnapshot).filter_by(
            account_id=account.id, month=month
        ).first()
        if existing:
            existing.value = value
        else:
            db.add(PatrimonySnapshot(
                account_id=account.id,
                month=month,
                value=value,
                note="Import tableau amortissement",
            ))
            created += 1

    return created


def migrate_cto_pea(db: Session, excel_path: str) -> int:
    """
    La feuille CTO_PEA a un header multi-niveau.
    On cible les colonnes (groupe, "Valeur MTM") pour chaque portefeuille.
    """
    df = pd.read_excel(excel_path, sheet_name="CTO_PEA", header=[0, 1])
    df.columns = ["__".join(str(c).strip() for c in col if "Unnamed" not in str(c)) for col in df.columns]

    # Mapping : partie du nom de colonne → nom compte en base
    targets = {
        # PEA Demo Broker Sam = MTM PEA directement
        # CTO Demo Broker Sam = Valeur MTM - MTM PEA  (géré séparément ci-dessous)
        "CTO Demo Broker Alex__Valeur MTM":         "CTO Demo Broker Alex",
        "TRD REP__Valeur MTM":               "TRD REP",
        "Crypto Demo__Valeur MTM":      "Crypto Demo",
        "trading (ava & xtb)__Valeur MTM":   "trading (ava & xtb)",
        "PEA Demo__Valeur MTM":   "PEA Demo",
    }

    date_col = df.columns[0]
    created = 0

    for col_key, account_name in targets.items():
        if col_key not in df.columns:
            continue
        account = _get_account(db, account_name)
        if not account:
            continue

        for _, row in df.iterrows():
            month = _parse_month(row[date_col])
            if not month:
                continue
            value = row.get(col_key)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            existing = db.query(PatrimonySnapshot).filter_by(
                account_id=account.id, month=month
            ).first()
            if existing:
                existing.value = value
            else:
                db.add(PatrimonySnapshot(
                    account_id=account.id, month=month, value=value,
                    note="Import Excel initial",
                ))
                created += 1

    # ── PEA Demo Broker Sam et CTO Demo Broker Sam (split Valeur MTM / MTM PEA) ──────────
    acc_pea = _get_account(db, "PEA Demo Broker Sam")
    acc_cto = _get_account(db, "CTO Demo Broker Sam")
    if acc_pea and acc_cto and "Demo Broker Sam__Valeur MTM" in df.columns and "Demo Broker Sam__MTM PEA" in df.columns:
        for _, row in df.iterrows():
            month = _parse_month(row[date_col])
            if not month:
                continue
            total = row.get("Demo Broker Sam__Valeur MTM")
            pea   = row.get("Demo Broker Sam__MTM PEA")
            if total is None or (isinstance(total, float) and pd.isna(total)):
                continue
            total = float(total)
            pea   = float(pea) if pea is not None and not (isinstance(pea, float) and pd.isna(pea)) else 0.0
            cto   = total - pea

            for acc, val in [(acc_pea, pea), (acc_cto, cto)]:
                if val <= 0:
                    continue
                existing = db.query(PatrimonySnapshot).filter_by(account_id=acc.id, month=month).first()
                if existing:
                    existing.value = val
                else:
                    db.add(PatrimonySnapshot(account_id=acc.id, month=month, value=val, note="Import Excel split"))
                    created += 1

    return created


def run_migration(db: Session, excel_path: str) -> dict:
    """Point d'entrée principal — importe toutes les feuilles."""
    results = {}

    try:
        xl = pd.ExcelFile(excel_path)
    except Exception as e:
        return {"error": str(e)}

    for sheet_name, col_pairs in SHEET_MAPPINGS.items():
        if not col_pairs:
            continue
        if sheet_name not in xl.sheet_names:
            results[sheet_name] = "feuille absente"
            continue
        df = xl.parse(sheet_name)
        count = migrate_sheet(db, df, col_pairs)
        results[sheet_name] = f"{count} snapshots créés"

    # CTO_PEA — header multi-niveau, traitement séparé
    try:
        count = migrate_cto_pea(db, excel_path)
        results["CTO_PEA"] = f"{count} snapshots créés"
    except Exception as e:
        results["CTO_PEA"] = f"erreur: {e}"

    # Prêt immo
    if "Prêt immo" in xl.sheet_names:
        df = xl.parse("Prêt immo")
        count = migrate_pret_immo(db, df)
        results["Prêt immo"] = f"{count} snapshots créés"

    db.commit()
    return results
