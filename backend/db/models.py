from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Boolean,
    ForeignKey, Table, Text, Enum as SAEnum, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from db.database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

class MemberRole(str, enum.Enum):
    owner = "owner"
    spouse = "spouse"
    child = "child"


class AccountType(str, enum.Enum):
    courant = "courant"
    epargne = "epargne"
    livret = "livret"
    cto = "cto"
    pea = "pea"
    per = "per"
    assurance_vie = "assurance_vie"
    immobilier = "immobilier"
    credit = "credit"
    autre_actif = "autre_actif"
    autre_passif = "autre_passif"


class AccountStatus(str, enum.Enum):
    actif = "actif"
    cloture = "cloture"
    archive = "archive"


class TransactionType(str, enum.Enum):
    debit = "debit"
    credit = "credit"


class RuleMatchType(str, enum.Enum):
    contains = "contains"
    startswith = "startswith"
    regex = "regex"


class RuleSource(str, enum.Enum):
    auto = "auto"
    user = "user"


class AgentRunStatus(str, enum.Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


class AgentImportDecisionValue(str, enum.Enum):
    imported = "imported"
    ignored = "ignored"


class ProjectionMode(str, enum.Enum):
    linear = "linear"
    fixed_historical = "fixed_historical"
    actual_only = "actual_only"


# ─── Table d'association compte ↔ membre ──────────────────────────────────────

account_members = Table(
    "account_members",
    Base.metadata,
    Column("account_id", Integer, ForeignKey("accounts.id"), primary_key=True),
    Column("member_id", Integer, ForeignKey("family_members.id"), primary_key=True),
)


# ─── Modèles ──────────────────────────────────────────────────────────────────

class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    role = Column(SAEnum(MemberRole), nullable=False)

    accounts = relationship("Account", secondary=account_members, back_populates="members")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(SAEnum(AccountType), nullable=False)
    bank = Column(String, nullable=True)
    currency = Column(String, default="EUR")
    initial_balance = Column(Float, default=0.0)
    start_date = Column(Date, nullable=True)
    status = Column(SAEnum(AccountStatus), default=AccountStatus.actif)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    members = relationship("FamilyMember", secondary=account_members, back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")
    patrimony_snapshots = relationship("PatrimonySnapshot", back_populates="account")
    provider_mappings = relationship("AccountProviderMapping", back_populates="account")


class CategoryGroup(Base):
    __tablename__ = "category_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    color = Column(String, default="#6b7280")
    sort_order = Column(Integer, default=0)
    budget_annual = Column(Float, nullable=True)        # budget annuel (€)
    exclude_from_budget = Column(Boolean, default=False) # flux investissement/épargne
    projection_mode = Column(SAEnum(ProjectionMode), default=ProjectionMode.linear, nullable=False)

    categories = relationship("Category", back_populates="group")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    color = Column(String, default="#6366f1")
    icon = Column(String, nullable=True)
    is_system = Column(Boolean, default=True)
    group_id = Column(Integer, ForeignKey("category_groups.id"), nullable=True)

    group = relationship("CategoryGroup", back_populates="categories")
    rules = relationship("CategoryRule", back_populates="category")
    transactions = relationship("Transaction", back_populates="category")


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String, nullable=False)
    match_type = Column(SAEnum(RuleMatchType), default=RuleMatchType.contains)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    priority = Column(Integer, default=0)
    source = Column(SAEnum(RuleSource), default=RuleSource.auto)
    created_at = Column(DateTime, default=func.now())

    category = relationship("Category", back_populates="rules")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    date = Column(Date, nullable=False)
    value_date = Column(Date, nullable=True)
    raw_label = Column(String, nullable=False)
    label = Column(String, nullable=False)
    amount = Column(Float, nullable=False)  # toujours positif
    transaction_type = Column(SAEnum(TransactionType), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category_source = Column(String, nullable=True)   # "auto" | "manual"
    is_internal_transfer = Column(Boolean, default=False)
    is_neutral           = Column(Boolean, default=False)  # flux neutre (créance, prêt...)
    is_investment        = Column(Boolean, default=False)  # investissement/épargne (exclu des dépenses)
    is_compte_pro        = Column(Boolean, default=False)  # apport compte pro (déduit des revenus)
    transfer_pair_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    import_hash = Column(String, unique=True, nullable=False)  # dédoublonnage
    created_at = Column(DateTime, default=func.now())

    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")


class PatrimonySnapshot(Base):
    __tablename__ = "patrimony_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    month = Column(String, nullable=False)   # format YYYY-MM
    value = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    account = relationship("Account", back_populates="patrimony_snapshots")


class PatrimonyDraftItem(Base):
    __tablename__ = "patrimony_draft_items"
    __table_args__ = (
        UniqueConstraint("account_id", "month", name="uq_patrimony_draft_account_month"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    month = Column(String, nullable=False)   # format YYYY-MM
    value = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    source_month = Column(String, nullable=True)
    source_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    account = relationship("Account")


class Settings(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CloudSave(Base):
    __tablename__ = "cloud_saves"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    github_sha = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    restored_at = Column(DateTime, nullable=True)


class AccountProviderMapping(Base):
    __tablename__ = "account_provider_mappings"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", name="uq_provider_account"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)
    provider_account_id = Column(String, nullable=False)
    local_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    external_name = Column(String, nullable=True)
    external_type = Column(String, nullable=True)
    currency = Column(String, default="EUR")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_seen_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="provider_mappings")


class ExternalTransaction(Base):
    __tablename__ = "external_transactions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_transaction_id", name="uq_provider_transaction"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)
    provider_transaction_id = Column(String, nullable=False)
    provider_account_id = Column(String, nullable=False)
    local_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    raw_payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    external_run_id = Column(String, nullable=True)
    status = Column(SAEnum(AgentRunStatus), nullable=False)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=False)
    accounts_count = Column(Integer, default=0)
    transactions_count = Column(Integer, default=0)
    snapshot_path = Column(String, nullable=True)
    message = Column(Text, nullable=True)

    errors = relationship("AgentRunError", back_populates="run")


class AgentRunError(Base):
    __tablename__ = "agent_run_errors"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False)
    provider_account_id = Column(String, nullable=True)
    severity = Column(String, default="error")
    code = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    raw_payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    run = relationship("AgentRun", back_populates="errors")


class SimulatorConfig(Base):
    __tablename__ = "simulator_config"

    id = Column(Integer, primary_key=True)
    monthly_contribution = Column(Float, default=500.0)
    annual_rate = Column(Float, default=8.0)
    account_types = Column(JSON, default=lambda: ["pea", "cto", "per", "assurance_vie"])
    milestone_step = Column(Float, default=100000.0)
    milestone_max = Column(Float, default=1000000.0)


class AgentImportDecision(Base):
    __tablename__ = "agent_import_decisions"
    __table_args__ = (
        UniqueConstraint("agent_name", "run_id", "item_id", name="uq_agent_import_decision_item"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    run_id = Column(String, nullable=False)
    item_id = Column(String, nullable=False)
    decision = Column(SAEnum(AgentImportDecisionValue), nullable=False)
    local_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
