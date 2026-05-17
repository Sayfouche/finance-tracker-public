"""
Import de relevés bancaires CSV / Excel.
Détecte automatiquement la structure, normalise et dédoublonne.
"""
import hashlib
import pandas as pd
from datetime import date, datetime
from sqlalchemy.orm import Session
from db.models import Transaction, TransactionType
from core.categorizer import normalize_label, categorize
from core.transfer_detector import detect_internal_transfers


# Formats testés dans l'ordre — du plus précis (ISO) au plus ambigu
_DATE_FORMATS = [
    "%Y-%m-%d",   # ISO : 2026-02-04
    "%d/%m/%Y",   # FR  : 04/02/2026
    "%d-%m-%Y",   # FR  : 04-02-2026
    "%d/%m/%y",   # FR court : 04/02/26
    "%d-%m-%y",   # FR court : 04-02-26
    "%m/%d/%Y",   # US  : 02/04/2026 (fallback)
]


def _parse_date(raw) -> date:
    """Parse une date en essayant les formats connus, priorité au format FR."""
    s = str(raw).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Dernier recours pandas
    return pd.to_datetime(raw, dayfirst=True).date()


# Noms de colonnes reconnus par type
DATE_COLS     = ["date", "dateop", "date opération", "date operation", "date de l'opération",
                 "date valeur", "dateval"]
LABEL_COLS    = ["libellé", "libelle", "description", "label", "opération", "operation",
                 "libelle operation", "libellé opération"]
SUPPLIER_COLS = ["supplierfound", "supplier_found", "supplier", "marchand"]
AMOUNT_COLS   = ["montant", "amount", "valeur", "montant operation", "montant opération"]
DEBIT_COLS    = ["débit", "debit", "sortie"]
CREDIT_COLS   = ["crédit", "credit", "entrée", "entree"]
BALANCE_COLS  = ["solde", "balance"]


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand in cols_lower:
            return cols_lower[cand]
    return None


def _make_hash(account_id: int, row_date: date, raw_label: str, amount: float) -> str:
    """Hash basé sur le libellé brut (pas normalisé) pour éviter les faux doublons."""
    key = f"{account_id}|{row_date}|{raw_label}|{amount:.2f}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _find_header_row(filepath: str, sep: str, encoding: str) -> int:
    """
    Cherche la ligne contenant les vrais en-têtes.
    Certaines banques ajoutent des lignes de métadonnées avant les colonnes.
    Retourne l'index (0-based) de la ligne d'en-tête, ou 0 par défaut.
    """
    header_keywords = {"date", "libelle", "libellé", "montant", "amount", "operation"}
    try:
        with open(filepath, encoding=encoding, errors="replace") as f:
            for i, line in enumerate(f):
                cells = [c.strip().lower() for c in line.split(sep)]
                if sum(1 for c in cells if any(k in c for k in header_keywords)) >= 2:
                    return i
    except Exception:
        pass
    return 0


def _find_excel_header_row(filepath: str) -> int:
    """
    Lit les premières lignes d'un fichier Excel pour trouver la ligne d'en-tête.
    Retourne l'index (0-based) de la ligne contenant les vraies colonnes.
    """
    header_keywords = {"date", "libelle", "libellé", "montant", "amount", "operation"}
    try:
        preview = pd.read_excel(filepath, header=None, nrows=10)
        for i, row in preview.iterrows():
            cells = [str(c).strip().lower() for c in row if pd.notna(c)]
            if sum(1 for c in cells if any(k in c for k in header_keywords)) >= 2:
                return int(i)
    except Exception:
        pass
    return 0


def parse_file(filepath: str) -> pd.DataFrame:
    """Lit un CSV ou Excel et retourne un DataFrame brut."""
    if filepath.endswith(".csv"):
        for sep in ["\t", ";", ","]:
            for encoding in ["utf-8", "latin-1"]:
                try:
                    skiprows = _find_header_row(filepath, sep, encoding)
                    df = pd.read_csv(filepath, sep=sep, encoding=encoding,
                                     skiprows=skiprows, on_bad_lines="skip")
                    if len(df.columns) > 1:
                        return df
                except Exception:
                    pass
        # Fallback
        return pd.read_csv(filepath, sep=";", encoding="latin-1")
    else:
        # Excel (.xls ou .xlsx) — détection de la ligne d'en-tête
        header_row = _find_excel_header_row(filepath)
        return pd.read_excel(filepath, skiprows=header_row)


def import_transactions(
    db: Session,
    account_id: int,
    filepath: str,
) -> dict:
    """
    Parse un fichier, crée les transactions manquantes et détecte les virements.
    Retourne un rapport d'import.
    """
    try:
        df = parse_file(filepath)
    except Exception as e:
        return {"error": f"Lecture fichier impossible : {e}"}
    df.columns = [str(c).strip() for c in df.columns]

    date_col     = _find_col(df, DATE_COLS)
    label_col    = _find_col(df, LABEL_COLS)
    supplier_col = _find_col(df, SUPPLIER_COLS)
    amount_col   = _find_col(df, AMOUNT_COLS)
    debit_col    = _find_col(df, DEBIT_COLS)
    credit_col   = _find_col(df, CREDIT_COLS)

    if not date_col or not label_col:
        return {"error": "Colonnes date ou libellé introuvables", "columns": list(df.columns)}

    created = skipped = errors = 0
    new_txs = []
    skipped_rows: list[dict] = []
    seen_hashes: set[str] = set()  # dédoublonnage intra-fichier

    for _, row in df.iterrows():
        try:
            # Date
            raw_date = row[date_col]
            tx_date = _parse_date(raw_date)

            # Libellé
            raw_label = str(row[label_col]).strip()
            # Certains exports enrichissent le libellé avec "NomMarchand | CARTE ..."
            # On prend la partie avant " | " si présente (déjà propre)
            if " | " in raw_label:
                clean_hint = raw_label.split(" | ")[0].strip()
            elif supplier_col and pd.notna(row.get(supplier_col)) and str(row[supplier_col]).strip() not in ("", "nan"):
                clean_hint = str(row[supplier_col]).strip()
            else:
                clean_hint = raw_label
            label = normalize_label(clean_hint)

            # Montant + sens
            if amount_col and amount_col in df.columns:
                amount = float(str(row[amount_col]).replace(",", ".").replace(" ", ""))
                tx_type = TransactionType.credit if amount >= 0 else TransactionType.debit
                amount = abs(amount)
            elif debit_col and credit_col:
                debit  = row.get(debit_col)
                credit = row.get(credit_col)
                d = float(str(debit).replace(",", ".").replace(" ", "")) if pd.notna(debit) and str(debit).strip() not in ("", "nan") else 0
                c = float(str(credit).replace(",", ".").replace(" ", "")) if pd.notna(credit) and str(credit).strip() not in ("", "nan") else 0
                if d > 0:
                    amount, tx_type = d, TransactionType.debit
                else:
                    amount, tx_type = c, TransactionType.credit
            else:
                errors += 1
                continue

            if amount == 0:
                skipped += 1
                skipped_rows.append({"date": str(tx_date), "label": raw_label, "amount": 0, "type": tx_type.value, "reason": "montant zéro"})
                continue

            # Dédoublonnage : en base ET dans le fichier courant
            import_hash = _make_hash(account_id, tx_date, raw_label, amount)
            if import_hash in seen_hashes or db.query(Transaction).filter_by(import_hash=import_hash).first():
                skipped += 1
                skipped_rows.append({"date": str(tx_date), "label": raw_label, "amount": amount, "type": tx_type.value, "reason": "doublon"})
                continue
            seen_hashes.add(import_hash)

            # Catégorisation
            category_id = categorize(label, db)

            tx = Transaction(
                account_id=account_id,
                date=tx_date,
                raw_label=raw_label,
                label=label,
                amount=amount,
                transaction_type=tx_type,
                category_id=category_id,
                category_source="auto" if category_id else None,
                import_hash=import_hash,
            )
            db.add(tx)
            new_txs.append(tx)
            created += 1

        except Exception:
            errors += 1

    db.flush()

    # Détection virements internes
    transfers = detect_internal_transfers(db, new_txs)
    db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "internal_transfers_detected": transfers,
        "skipped_detail": skipped_rows,
    }
