"""
Crée la table category_groups, ajoute group_id aux categories, et seed les groupes par défaut.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.database import Base, engine, SessionLocal
from db.models import CategoryGroup, Category, ProjectionMode

# Créer les nouvelles tables / colonnes
Base.metadata.create_all(bind=engine)

# Migration : ajouter group_id si absent
with engine.connect() as conn:
    cols = [row[1] for row in conn.execute(
        __import__("sqlalchemy").text("PRAGMA table_info(categories)")
    )]
    if "group_id" not in cols:
        conn.execute(__import__("sqlalchemy").text(
            "ALTER TABLE categories ADD COLUMN group_id INTEGER REFERENCES category_groups(id)"
        ))
        conn.commit()
    group_cols = [row[1] for row in conn.execute(
        __import__("sqlalchemy").text("PRAGMA table_info(category_groups)")
    )]
    if "projection_mode" not in group_cols:
        conn.execute(__import__("sqlalchemy").text(
            "ALTER TABLE category_groups ADD COLUMN projection_mode VARCHAR(32) NOT NULL DEFAULT 'linear'"
        ))
        conn.commit()

GROUPS = [
    {"name": "Alimentation",      "color": "#22c55e", "sort_order": 1,
     "projection_mode": ProjectionMode.linear,
     "categories": ["Alimentation", "Boucherie"]},
    {"name": "Loisirs & Sorties", "color": "#06b6d4", "sort_order": 2,
     "projection_mode": ProjectionMode.actual_only,
     "categories": ["Restaurant", "Loisirs", "Voyage"]},
    {"name": "Soin & Mode",       "color": "#ec4899", "sort_order": 3,
     "projection_mode": ProjectionMode.linear,
     "categories": ["Cosmétique", "Habille", "Hygiéne"]},
    {"name": "Logement",          "color": "#3b82f6", "sort_order": 4,
     "projection_mode": ProjectionMode.fixed_historical,
     "categories": ["Logement"]},
    {"name": "Santé",             "color": "#ef4444", "sort_order": 5,
     "projection_mode": ProjectionMode.linear,
     "categories": ["Santé"]},
    {"name": "Transport",         "color": "#f59e0b", "sort_order": 6,
     "projection_mode": ProjectionMode.linear,
     "categories": ["Transport"]},
    {"name": "Abonnements",       "color": "#8b5cf6", "sort_order": 7,
     "projection_mode": ProjectionMode.fixed_historical,
     "categories": ["Telecom", "Abonnements"]},
    {"name": "Famille",           "color": "#f472b6", "sort_order": 8,
     "projection_mode": ProjectionMode.linear,
     "categories": ["Enfants"]},
    {"name": "Solidarité",        "color": "#84cc16", "sort_order": 9,
     "projection_mode": ProjectionMode.linear,
     "categories": ["Aide Familiale", "Zakaat"]},
    {"name": "Banque & Assurance","color": "#64748b", "sort_order": 10,
     "projection_mode": ProjectionMode.fixed_historical,
     "categories": ["Banque", "Assurance", "Retrait"]},
    {"name": "Impôts",            "color": "#94a3b8", "sort_order": 11,
     "projection_mode": ProjectionMode.fixed_historical,
     "categories": ["Impôts"]},
    {"name": "Autre",             "color": "#6b7280", "sort_order": 12,
     "projection_mode": ProjectionMode.actual_only,
     "categories": ["Autre"]},
]

db = SessionLocal()
try:
    for g in GROUPS:
        group = db.query(CategoryGroup).filter_by(name=g["name"]).first()
        if not group:
            group = CategoryGroup(name=g["name"], color=g["color"], sort_order=g["sort_order"])
            db.add(group)
            db.flush()
        else:
            group.color = g["color"]
            group.sort_order = g["sort_order"]
        group.projection_mode = g["projection_mode"]

        for cat_name in g["categories"]:
            cat = db.query(Category).filter_by(name=cat_name).first()
            if cat:
                cat.group_id = group.id

    db.commit()
    print("Groupes créés et catégories assignées.")
finally:
    db.close()
