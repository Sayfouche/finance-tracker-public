"use client";
import { useState, useEffect, useMemo } from "react";
import { ChevronDown, ChevronRight, Layers3, Plus, X } from "lucide-react";

import { API_BASE } from "@/lib/config";

const typeColors: Record<string, string> = {
  courant:       "bg-blue-500/15 text-blue-400",
  epargne:       "bg-teal-500/15 text-teal-400",
  livret:        "bg-emerald-500/15 text-emerald-400",
  cto:           "bg-violet-500/15 text-violet-400",
  pea:           "bg-violet-500/15 text-violet-400",
  per:           "bg-amber-500/15 text-amber-400",
  assurance_vie: "bg-cyan-500/15 text-cyan-400",
  immobilier:    "bg-orange-500/15 text-orange-400",
  credit:        "bg-red-500/15 text-red-400",
};

const typeLabels: Record<string, string> = {
  courant: "Courant", epargne: "Épargne", livret: "Livret",
  cto: "CTO", pea: "PEA", per: "PER",
  assurance_vie: "AV", immobilier: "Immobilier",
  credit: "Crédit", immobilier_equity: "Immobilier equity",
  autre_actif: "Actif", autre_passif: "Passif",
};

const typeOrder = ["courant", "epargne", "livret", "cto", "pea", "per", "assurance_vie", "immobilier_equity", "autre_actif", "autre_passif"];

const fmt = (v: number | null) =>
  v == null ? "—" : v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

const fmtMonth = (m: string) => {
  const [y, mo] = m.split("-");
  return new Date(Number(y), Number(mo) - 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
};

interface AccountRow {
  account_id: number;
  account_name: string;
  account_type: string;
  bank: string | null;
  members: string[];
  value: number | null;
  month: string;
}

interface Snapshot {
  month: string;
  accounts: AccountRow[];
  totals: { actifs: number; passifs: number; patrimoine_net: number };
}

interface Member {
  id: number;
  first_name: string;
  role: string;
}

interface Account {
  id: number;
  name: string;
  type: string;
  bank: string | null;
  currency: string;
  initial_balance: number;
  start_date: string | null;
  status: string;
  members: Member[];
  current_balance: number | null;
}

interface AccountForm {
  name: string;
  type: string;
  bank: string;
  currency: string;
  initial_balance: string;
  start_date: string;
  member_ids: number[];
}

const emptyForm: AccountForm = {
  name: "",
  type: "courant",
  bank: "",
  currency: "EUR",
  initial_balance: "0",
  start_date: new Date().toISOString().slice(0, 10),
  member_ids: [],
};

export default function AccountsClient({ months }: { months: string[] }) {
  const [selectedMonth, setSelectedMonth] = useState(months[0] ?? "");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AccountForm>(emptyForm);
  const [newMemberName, setNewMemberName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const reloadAccounts = async () => {
    const data = await fetch(`${API_BASE}/accounts/`, { cache: "no-store" }).then(r => r.json());
    setAccounts(data);
  };

  const reloadMembers = async () => {
    const data = await fetch(`${API_BASE}/members/`, { cache: "no-store" }).then(r => r.json());
    setMembers(data);
  };

  useEffect(() => {
    reloadAccounts().catch(() => {});
    reloadMembers().catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedMonth) return;
    setLoading(true);
    fetch(`${API_BASE}/patrimony/snapshot?month=${selectedMonth}`, { cache: "no-store" })
      .then(r => r.json())
      .then(data => { setSnapshot(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [selectedMonth]);

  const groups = useMemo(() => typeOrder.map(type => {
    const sourceTypes = type === "immobilier_equity" ? ["immobilier", "credit"] : [type];
    const accounts = snapshot?.accounts
      .filter(account => sourceTypes.includes(account.account_type))
      .sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0)) ?? [];
    const total = accounts.reduce((sum, account) => sum + (account.value ?? 0), 0);
    const positiveTotal = accounts.reduce((sum, account) => sum + Math.max(account.value ?? 0, 0), 0);
    return {
      type,
      label: typeLabels[type] ?? type,
      accounts,
      total,
      positiveTotal,
    };
  }).filter(group => group.accounts.length > 0), [snapshot]);

  useEffect(() => {
    if (groups.length === 0) return;
    setExpanded(current => {
      if (Object.keys(current).length > 0) return current;
      return { [groups[0].type]: true };
    });
  }, [groups]);

  const patrimoineNet = snapshot?.totals.patrimoine_net ?? 0;

  const toggleGroup = (type: string) => setExpanded(current => (
    { ...current, [type]: !current[type] }
  ));

  const topAccount = (accounts: AccountRow[]) =>
    accounts.slice().sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0))[0]
  ;

  const toggleMember = (memberId: number) => {
    setForm(current => ({
      ...current,
      member_ids: current.member_ids.includes(memberId)
        ? current.member_ids.filter(id => id !== memberId)
        : [...current.member_ids, memberId],
    }));
  };

  const createMember = async () => {
    const first_name = newMemberName.trim();
    if (!first_name) return;
    setFormError(null);
    const res = await fetch(`${API_BASE}/members/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ first_name, role: members.length === 0 ? "owner" : "spouse" }),
    });
    if (!res.ok) {
      setFormError("Impossible de créer ce titulaire.");
      return;
    }
    const member = await res.json();
    setMembers(current => [...current, member]);
    setForm(current => ({ ...current, member_ids: [...current.member_ids, member.id] }));
    setNewMemberName("");
  };

  const createAccount = async () => {
    const name = form.name.trim();
    if (!name) {
      setFormError("Le nom du compte est requis.");
      return;
    }
    setSaving(true);
    setFormError(null);
    const res = await fetch(`${API_BASE}/accounts/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        type: form.type,
        bank: form.bank.trim() || null,
        currency: form.currency.trim() || "EUR",
        initial_balance: Number(form.initial_balance || 0),
        start_date: form.start_date || null,
        member_ids: form.member_ids,
      }),
    });
    setSaving(false);
    if (!res.ok) {
      setFormError("Impossible de créer ce compte.");
      return;
    }
    setForm(emptyForm);
    setShowForm(false);
    await reloadAccounts().catch(() => {});
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Comptes</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Snapshot mensuel — {months.length} mois disponibles
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3 py-2 text-sm font-medium text-indigo-200 transition-colors hover:bg-indigo-500/25"
          >
            <Plus size={15} />
            Compte
          </button>
          <select
            value={selectedMonth}
            onChange={e => setSelectedMonth(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none"
          >
            {months.map(m => (
              <option key={m} value={m}>{fmtMonth(m)}</option>
            ))}
          </select>
        </div>
      </div>

      {showForm && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Nouveau compte</h2>
            <button onClick={() => setShowForm(false)} className="text-slate-500 hover:text-slate-300">
              <X size={16} />
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <input
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              placeholder="Nom du compte"
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
            />
            <select
              value={form.type}
              onChange={e => setForm({ ...form, type: e.target.value })}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
            >
              {Object.entries(typeLabels)
                .filter(([value]) => value !== "immobilier_equity")
                .map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <input
              value={form.bank}
              onChange={e => setForm({ ...form, bank: e.target.value })}
              placeholder="Banque / organisme"
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
            />
            <div className="grid grid-cols-[1fr_120px] gap-3">
              <input
                type="number"
                value={form.initial_balance}
                onChange={e => setForm({ ...form, initial_balance: e.target.value })}
                placeholder="Solde initial"
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
              />
              <input
                value={form.currency}
                onChange={e => setForm({ ...form, currency: e.target.value.toUpperCase().slice(0, 3) })}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
              />
            </div>
            <input
              type="date"
              value={form.start_date}
              onChange={e => setForm({ ...form, start_date: e.target.value })}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
            />
            <div className="rounded-lg border border-slate-800 bg-slate-950/35 p-3">
              <p className="mb-2 text-xs font-medium text-slate-400">Titulaire(s)</p>
              <div className="flex flex-wrap gap-2">
                {members.map(member => (
                  <button
                    key={member.id}
                    type="button"
                    onClick={() => toggleMember(member.id)}
                    className={`rounded border px-2 py-1 text-xs transition-colors ${
                      form.member_ids.includes(member.id)
                        ? "border-indigo-500/50 bg-indigo-500/20 text-indigo-200"
                        : "border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {member.first_name}
                  </button>
                ))}
              </div>
              <div className="mt-3 flex gap-2">
                <input
                  value={newMemberName}
                  onChange={e => setNewMemberName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && createMember()}
                  placeholder="Ajouter un titulaire"
                  className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-800 px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500"
                />
                <button onClick={createMember} className="rounded-lg border border-slate-700 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800">
                  Ajouter
                </button>
              </div>
            </div>
          </div>
          {formError && <p className="mt-3 text-xs text-red-400">{formError}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-400 hover:text-slate-200">
              Annuler
            </button>
            <button
              onClick={createAccount}
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving ? "Création..." : "Créer"}
            </button>
          </div>
        </div>
      )}

      {accounts.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Comptes configurés</h2>
            <span className="text-xs text-slate-500">{accounts.length} compte{accounts.length > 1 ? "s" : ""}</span>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {accounts.map(account => (
              <div key={account.id} className="rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-200">{account.name}</p>
                    <p className="truncate text-xs text-slate-500">
                      {[typeLabels[account.type] ?? account.type, account.bank, account.members.map(m => m.first_name).join(", ")].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm font-semibold text-slate-200">{fmt(account.current_balance)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Totaux */}
      {snapshot && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Total actifs",    value: snapshot.totals.actifs,         color: "text-emerald-400" },
            { label: "Total passifs",   value: snapshot.totals.passifs,        color: "text-red-400" },
            { label: "Patrimoine net",  value: snapshot.totals.patrimoine_net, color: "text-indigo-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <p className="text-xs text-slate-400 mb-1">{label}</p>
              <p className={`text-2xl font-bold ${color}`}>{fmt(value)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Agrégation comptes */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="text-center py-12 text-slate-500 text-sm">Chargement...</div>
        ) : (
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
              <div className="flex items-center gap-2">
                <Layers3 size={17} className="text-indigo-400" />
                <h2 className="text-sm font-semibold text-white">Agrégation par catégorie</h2>
              </div>
              <span className="text-xs text-slate-500">{selectedMonth ? fmtMonth(selectedMonth) : "—"}</span>
            </div>

            {groups.map(group => {
              const isOpen = !!expanded[group.type];
              const share = patrimoineNet > 0 && group.total > 0
                ? (group.total / patrimoineNet) * 100
                : 0;
              const leader = topAccount(group.accounts);
              return (
                <div key={group.type} className="border-b border-slate-800/70 last:border-0">
                  <button
                    onClick={() => toggleGroup(group.type)}
                    className="grid w-full grid-cols-[1fr_auto] gap-4 px-5 py-4 text-left transition-colors hover:bg-slate-800/35 md:grid-cols-[1fr_160px_140px]"
                  >
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-3">
                        {isOpen ? <ChevronDown size={17} className="text-slate-500" /> : <ChevronRight size={17} className="text-slate-500" />}
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${typeColors[group.type] ?? "bg-slate-700 text-slate-400"}`}>
                          {group.label}
                        </span>
                        <span className="truncate text-sm font-medium text-slate-100">
                          {group.accounts.length} compte{group.accounts.length > 1 ? "s" : ""}
                        </span>
                      </div>
                      <p className="mt-1 truncate pl-7 text-xs text-slate-500">
                        Principal: {leader?.account_name ?? "—"}
                      </p>
                    </div>
                    <div className="hidden self-center md:block">
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full bg-indigo-500"
                          style={{ width: `${Math.max(3, Math.min(100, share))}%` }}
                        />
                      </div>
                      <p className="mt-1 text-right text-[11px] text-slate-500">
                        {share > 0 ? `${share.toFixed(1)} % net` : "hors net"}
                      </p>
                    </div>
                    <div className={`self-center text-right text-base font-semibold ${
                      group.total < 0 ? "text-red-400" : "text-white"
                    }`}>
                      {fmt(group.total)}
                    </div>
                  </button>

                  {isOpen && (
                    <div className="border-t border-slate-800 bg-slate-950/35">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-xs uppercase tracking-wider text-slate-500">
                            <th className="px-12 py-3 text-left">Compte</th>
                            <th className="px-5 py-3 text-left">Titulaire</th>
                            <th className="px-5 py-3 text-right">Solde</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.accounts.map(account => (
                            <tr key={account.account_id} className="border-t border-slate-800/70 hover:bg-slate-800/25">
                              <td className="px-12 py-3">
                                <p className="font-medium text-slate-200">{account.account_name}</p>
                                {account.bank && <p className="text-xs text-slate-500">{account.bank}</p>}
                              </td>
                              <td className="px-5 py-3 text-xs text-slate-400">
                                {account.members.join(", ") || "—"}
                              </td>
                              <td className={`px-5 py-3 text-right font-semibold ${
                                account.value == null ? "text-slate-600" :
                                account.value >= 0 ? "text-white" : "text-red-400"
                              }`}>
                                {fmt(account.value)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}

            {groups.length === 0 && (
              <div className="px-5 py-10 text-center text-sm text-slate-500">
                Aucun compte valorisé pour ce mois.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
