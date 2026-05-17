"""
Public-safe system seed.

This seed only creates generic categories, rules and settings. Demo users,
accounts and transactions live in ``backend/scripts/seed_demo_data.py`` so a
fresh public install does not expose a personal account structure.
"""
from sqlalchemy.orm import Session

from db.models import Category, CategoryRule, RuleMatchType, RuleSource, Settings


def seed_categories(db: Session) -> dict[str, Category]:
    existing = {c.name: c for c in db.query(Category).all()}
    if existing:
        return existing

    categories_data = [
        ("Alimentation", "#22c55e", "shopping-cart"),
        ("Logement", "#3b82f6", "home"),
        ("Transport", "#f59e0b", "car"),
        ("Enfants", "#ec4899", "baby"),
        ("Santé", "#ef4444", "heart"),
        ("Abonnements", "#8b5cf6", "repeat"),
        ("Loisirs", "#06b6d4", "music"),
        ("Impôts", "#64748b", "landmark"),
        ("Épargne", "#10b981", "piggy-bank"),
        ("Investissement", "#6366f1", "trending-up"),
        ("Revenus", "#84cc16", "wallet"),
        ("Virement interne", "#94a3b8", "arrow-left-right"),
        ("Banque", "#64748b", "building-2"),
        ("Assurance", "#64748b", "shield"),
        ("Telecom", "#0ea5e9", "wifi"),
        ("Autre", "#6b7280", "circle"),
    ]

    categories: dict[str, Category] = {}
    for name, color, icon in categories_data:
        category = Category(name=name, color=color, icon=icon, is_system=True)
        db.add(category)
        categories[name] = category
    db.flush()
    return categories


def seed_rules(db: Session, categories: dict[str, Category]) -> None:
    if db.query(CategoryRule).first():
        return

    rules_data = [
        ("carrefour", RuleMatchType.contains, "Alimentation", 10),
        ("lidl", RuleMatchType.contains, "Alimentation", 10),
        ("supermarket", RuleMatchType.contains, "Alimentation", 10),
        ("grocery", RuleMatchType.contains, "Alimentation", 10),
        ("rent", RuleMatchType.contains, "Logement", 10),
        ("loyer", RuleMatchType.contains, "Logement", 10),
        ("energy", RuleMatchType.contains, "Logement", 10),
        ("electricite", RuleMatchType.contains, "Logement", 10),
        ("mortgage", RuleMatchType.contains, "Logement", 10),
        ("echeance pret", RuleMatchType.contains, "Logement", 10),
        ("phone", RuleMatchType.contains, "Telecom", 10),
        ("internet", RuleMatchType.contains, "Telecom", 10),
        ("mobile", RuleMatchType.contains, "Telecom", 10),
        ("bank fee", RuleMatchType.contains, "Banque", 10),
        ("commission", RuleMatchType.contains, "Banque", 10),
        ("cotisation", RuleMatchType.contains, "Banque", 10),
        ("insurance", RuleMatchType.contains, "Assurance", 10),
        ("assurance", RuleMatchType.contains, "Assurance", 10),
        ("train", RuleMatchType.contains, "Transport", 10),
        ("metro", RuleMatchType.contains, "Transport", 10),
        ("fuel", RuleMatchType.contains, "Transport", 10),
        ("uber", RuleMatchType.contains, "Transport", 10),
        ("pharmacy", RuleMatchType.contains, "Santé", 10),
        ("pharmacie", RuleMatchType.contains, "Santé", 10),
        ("doctor", RuleMatchType.contains, "Santé", 10),
        ("netflix", RuleMatchType.contains, "Abonnements", 10),
        ("spotify", RuleMatchType.contains, "Abonnements", 10),
        ("amazon", RuleMatchType.contains, "Abonnements", 10),
        ("apple", RuleMatchType.contains, "Abonnements", 10),
        ("restaurant", RuleMatchType.contains, "Loisirs", 10),
        ("cinema", RuleMatchType.contains, "Loisirs", 10),
        ("booking", RuleMatchType.contains, "Loisirs", 10),
        ("tax", RuleMatchType.contains, "Impôts", 10),
        ("impot", RuleMatchType.contains, "Impôts", 10),
        ("tresor", RuleMatchType.contains, "Impôts", 10),
        ("savings", RuleMatchType.contains, "Épargne", 10),
        ("livret", RuleMatchType.contains, "Épargne", 10),
        ("broker", RuleMatchType.contains, "Investissement", 10),
        ("etf", RuleMatchType.contains, "Investissement", 10),
        ("salary", RuleMatchType.contains, "Revenus", 10),
        ("salaire", RuleMatchType.contains, "Revenus", 10),
        ("school", RuleMatchType.contains, "Enfants", 10),
        ("ecole", RuleMatchType.contains, "Enfants", 10),
    ]

    for pattern, match_type, category_name, priority in rules_data:
        category = categories.get(category_name)
        if not category:
            continue
        db.add(CategoryRule(
            pattern=pattern,
            match_type=match_type,
            category_id=category.id,
            priority=priority,
            source=RuleSource.auto,
        ))


def seed_settings(db: Session) -> None:
    defaults = {
        "taux_rendement_annuel": "0.05",
        "scenario_maison": "central",
        "taux_appreciation_maison": "0.01",
        "surface_maison_m2": "0",
        "valeur_maison_achat": "0",
        "date_achat_maison": "",
    }
    existing = {setting.key for setting in db.query(Settings).all()}
    for key, value in defaults.items():
        if key not in existing:
            db.add(Settings(key=key, value=value))


def run_seed(db: Session) -> None:
    categories = seed_categories(db)
    seed_rules(db, categories)
    seed_settings(db)
    db.commit()
