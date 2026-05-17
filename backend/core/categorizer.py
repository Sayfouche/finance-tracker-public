"""
Moteur de catégorisation des transactions par règles sur le libellé.
Les règles utilisateur (source=user) sont prioritaires sur les règles auto.
"""
import re
from sqlalchemy.orm import Session
from db.models import CategoryRule, RuleMatchType, RuleSource


def normalize_label(raw: str) -> str:
    """Nettoie un libellé bancaire brut pour obtenir un identifiant stable."""
    label = raw.lower().strip()
    # Supprimer tout ce qui suit "du JJ/MM/AA" (suffixe CB : date + ville + carte)
    label = re.sub(r"\bdu\s+\d{1,2}/\d{1,2}/\d{2,4}\b.*$", " ", label)
    # Dates résiduelles (ISO ou courtes)
    label = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", label)
    label = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", " ", label)
    # Séquences de 4+ chiffres (numéros de carte, références)
    label = re.sub(r"\d{4,}", " ", label)
    # Références REF, MOTIF, EMETTEUR en fin de libellé
    label = re.sub(r"\b(ref|motif|emetteur|lib)\s*:?\s*\S+.*$", " ", label)
    # Artefacts résiduels : "- carte*", tirets isolés en fin
    label = re.sub(r"\s*-\s*carte\*?\s*\w*", " ", label)
    label = re.sub(r"\s*[-–]\s*$", " ", label)
    label = re.sub(r"\s+", " ", label).strip()
    return label


def categorize(label: str, db: Session) -> int | None:
    """
    Retourne l'id de la catégorie correspondante ou None.
    Priorité : rules user > rules auto, priority décroissante.
    """
    label_lower = label.lower()

    rules = (
        db.query(CategoryRule)
        .order_by(
            # user avant auto
            CategoryRule.source.desc(),
            CategoryRule.priority.desc(),
        )
        .all()
    )

    for rule in rules:
        match = False
        if rule.match_type == RuleMatchType.contains:
            match = rule.pattern.lower() in label_lower
        elif rule.match_type == RuleMatchType.startswith:
            match = label_lower.startswith(rule.pattern.lower())
        elif rule.match_type == RuleMatchType.regex:
            try:
                match = bool(re.search(rule.pattern, label_lower))
            except re.error:
                pass

        if match:
            return rule.category_id

    return None
