"""Tests du moteur de catégorisation."""
from core.categorizer import normalize_label, categorize
from db.models import Category, CategoryRule, RuleMatchType, RuleSource


def _setup_categories(db):
    cats = {}
    for name, color in [("Alimentation", "#22c55e"), ("Transport", "#f59e0b"), ("Autre", "#6b7280")]:
        c = Category(name=name, color=color, is_system=True)
        db.add(c)
        cats[name] = c
    db.flush()
    # Règles
    db.add(CategoryRule(pattern="carrefour", match_type=RuleMatchType.contains,
                        category_id=cats["Alimentation"].id, priority=10, source=RuleSource.auto))
    db.add(CategoryRule(pattern="sncf", match_type=RuleMatchType.contains,
                        category_id=cats["Transport"].id, priority=10, source=RuleSource.auto))
    db.commit()
    return cats


class TestNormalizeLabel:
    def test_lowercase(self):
        assert normalize_label("CARREFOUR CITY") == "carrefour city"

    def test_removes_long_numbers(self):
        result = normalize_label("VIR SEPA 123456789")
        assert "123456789" not in result

    def test_strips_whitespace(self):
        assert normalize_label("  RATP  ") == "ratp"


class TestCategorize:
    def test_matches_alimentation(self, db):
        cats = _setup_categories(db)
        result = categorize("paiement carrefour city paris", db)
        assert result == cats["Alimentation"].id

    def test_matches_transport(self, db):
        cats = _setup_categories(db)
        result = categorize("billet sncf lyon paris", db)
        assert result == cats["Transport"].id

    def test_no_match_returns_none(self, db):
        _setup_categories(db)
        result = categorize("virement michel dupont", db)
        assert result is None

    def test_user_rule_overrides_auto(self, db):
        cats = _setup_categories(db)
        # Règle user qui reclasse "carrefour" en Transport
        db.add(CategoryRule(
            pattern="carrefour", match_type=RuleMatchType.contains,
            category_id=cats["Transport"].id, priority=100, source=RuleSource.user
        ))
        db.commit()
        result = categorize("carrefour market", db)
        assert result == cats["Transport"].id

    def test_case_insensitive(self, db):
        cats = _setup_categories(db)
        result = categorize("CARREFOUR MARKET", db)
        assert result == cats["Alimentation"].id
