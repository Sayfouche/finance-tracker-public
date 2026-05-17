"use client";
import { useState, useEffect } from "react";

import { API_BASE } from "@/lib/config";

interface Category { id: number; name: string; color: string }
interface Group {
  id: number;
  name: string;
  color: string;
  sort_order: number;
  budget_annual: number | null;
  budget_monthly: number | null;
  exclude_from_budget: boolean;
  projection_mode: ProjectionMode;
  categories: Category[];
}

type ProjectionMode = "linear" | "fixed_historical" | "actual_only";

const PROJECTION_MODE_LABELS: Record<ProjectionMode, string> = {
  linear: "Lissé sur le mois",
  fixed_historical: "Fixe · moyenne 6 mois",
  actual_only: "Réel uniquement",
};

interface DistributionItem {
  group_id: number;
  group_name: string;
  group_color: string;
  avg_monthly: number;
  suggested_annual: number;
  suggested_monthly: number;
  proportion_pct: number;
}

export default function SettingsPage() {
  const [groups, setGroups]           = useState<Group[]>([]);
  const [allCats, setAllCats]         = useState<Category[]>([]);
  const [editingGroup, setEditingGroup]   = useState<Group | null>(null);
  const [savingLimit, setSavingLimit]     = useState<number | null>(null);
  const [limitInputs, setLimitInputs]     = useState<Record<number, string>>({});
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupColor, setNewGroupColor] = useState("#6b7280");
  const [toastMsg, setToastMsg]       = useState<string | null>(null);
  const [movingCat, setMovingCat]     = useState<{ cat: Category; fromGroupId: number } | null>(null);

  // Global budget distribution (mensuel, réparti en annuel par groupe)
  const [globalBudget, setGlobalBudget]   = useState("5000");
  const [historyMonths, setHistoryMonths] = useState("3");
  const [distribution, setDistribution]   = useState<DistributionItem[] | null>(null);
  const [distribLoading, setDistribLoading] = useState(false);
  const [applying, setApplying]           = useState(false);

  function showToast(msg: string) {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  }

  async function simulateDistribution() {
    const budget = parseFloat(globalBudget.replace(",", "."));
    const months = parseInt(historyMonths, 10);
    if (!budget || budget <= 0 || !months || months < 1) return;
    setDistribLoading(true);
    try {
      const res = await fetch(`${API_BASE}/category-groups/distribute-budget`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ total_monthly_budget: budget, months_history: months, apply: false }),
      });
      const data = await res.json();
      setDistribution(data);
    } finally {
      setDistribLoading(false);
    }
  }

  async function applyDistribution() {
    const budget = parseFloat(globalBudget.replace(",", "."));
    const months = parseInt(historyMonths, 10);
    if (!budget || budget <= 0 || !months || months < 1) return;
    setApplying(true);
    try {
      const res = await fetch(`${API_BASE}/category-groups/distribute-budget`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ total_monthly_budget: budget, months_history: months, apply: true }),
      });
      const data = await res.json();
      setDistribution(data);
      showToast("Budgets appliqués");
      load();
    } finally {
      setApplying(false);
    }
  }

  function fmtCurrency(amount: number) {
    return amount.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  }

  async function load() {
    const [g, c] = await Promise.all([
      fetch(`${API_BASE}/category-groups/`).then(r => r.json()),
      fetch(`${API_BASE}/categories/`).then(r => r.json()),
    ]);
    setGroups(g);
    setAllCats(c);
    const inputs: Record<number, string> = {};
    g.forEach((gr: Group) => {
      inputs[gr.id] = gr.budget_annual ? String(gr.budget_annual) : "";
    });
    setLimitInputs(inputs);
  }

  useEffect(() => { load(); }, []);

  async function saveBudgetLimit(groupId: number) {
    setSavingLimit(groupId);
    const raw = limitInputs[groupId] ?? "";
    const value = raw === "" ? 0 : parseFloat(raw.replace(",", "."));
    await fetch(`${API_BASE}/category-groups/${groupId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ budget_annual: value }),
    });
    setSavingLimit(null);
    showToast("Budget annuel enregistré");
    load();
  }

  async function saveProjectionMode(groupId: number, projectionMode: ProjectionMode) {
    await fetch(`${API_BASE}/category-groups/${groupId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projection_mode: projectionMode }),
    });
    showToast("Projection enregistrée");
    load();
  }

  // Catégories sans groupe
  const unassigned = allCats.filter(c =>
    !groups.some(g => g.categories.some(gc => gc.id === c.id))
  ).filter(c => !["Investissement", "Épargne", "Virement interne", "Compte pro", "Revenus"].includes(c.name));

  async function createGroup() {
    if (!newGroupName.trim()) return;
    await fetch(`${API_BASE}/category-groups/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newGroupName.trim(), color: newGroupColor, sort_order: groups.length + 1 }),
    });
    setNewGroupName("");
    showToast("Groupe créé");
    load();
  }

  async function saveGroup(g: Group) {
    await fetch(`${API_BASE}/category-groups/${g.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: g.name, color: g.color, sort_order: g.sort_order }),
    });
    setEditingGroup(null);
    showToast("Groupe mis à jour");
    load();
  }

  async function deleteGroup(id: number) {
    if (!confirm("Supprimer ce groupe ? Les catégories seront désassignées.")) return;
    await fetch(`${API_BASE}/category-groups/${id}`, { method: "DELETE" });
    showToast("Groupe supprimé");
    load();
  }

  async function moveCategory(catId: number, targetGroupId: number) {
    await fetch(`${API_BASE}/category-groups/${targetGroupId}/assign-category/${catId}`, { method: "PATCH" });
    setMovingCat(null);
    load();
  }

  async function unassignCategory(catId: number) {
    await fetch(`${API_BASE}/category-groups/unassign-category/${catId}`, { method: "PATCH" });
    load();
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Paramètres</h1>
        <p className="text-sm text-slate-500 mt-0.5">Gérez les grands groupes de catégories pour la vue budget simplifiée</p>
      </div>

      {/* Budget global */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-300">Répartition automatique du budget</h2>
          <p className="text-xs text-slate-500 mt-0.5">Saisir le budget mensuel global — calcule automatiquement le budget annuel par groupe</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 shrink-0">Total</span>
            <input
              type="number"
              min="0"
              value={globalBudget}
              onChange={e => setGlobalBudget(e.target.value)}
              className="w-28 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500 tabular-nums"
            />
            <span className="text-xs text-slate-500">€</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 shrink-0">sur les</span>
            <input
              type="number"
              min="1"
              max="24"
              value={historyMonths}
              onChange={e => setHistoryMonths(e.target.value)}
              className="w-16 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500 tabular-nums text-center"
            />
            <span className="text-xs text-slate-500 shrink-0">derniers mois</span>
          </div>
          <button
            onClick={simulateDistribution}
            disabled={distribLoading}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm rounded-lg transition-colors"
          >
            {distribLoading ? "…" : "Simuler"}
          </button>
        </div>

        {distribution && distribution.length > 0 && (
          <div className="space-y-3">
            <div className="overflow-hidden rounded-lg border border-slate-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-800/60 text-left">
                    <th className="px-4 py-2.5 text-xs font-medium text-slate-400">Groupe</th>
                    <th className="px-4 py-2.5 text-xs font-medium text-slate-400 text-right">Moy. /mois</th>
                    <th className="px-4 py-2.5 text-xs font-medium text-slate-400 text-right">Budget annuel</th>
                    <th className="px-4 py-2.5 text-xs font-medium text-slate-400 text-right">(/mois)</th>
                    <th className="px-4 py-2.5 text-xs font-medium text-slate-400 text-right">%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">

                  {distribution.map(item => (
                    <tr key={item.group_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.group_color }} />
                          <span className="text-slate-300">{item.group_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-400">
                        {fmtCurrency(item.avg_monthly)}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        <span className="font-semibold text-indigo-400">{fmtCurrency(item.suggested_annual)}</span>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-500">
                        {fmtCurrency(item.suggested_monthly)}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-slate-500">
                        {item.proportion_pct}%
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-slate-800/80 border-t-2 border-slate-700">
                    <td className="px-4 py-2.5 text-xs font-semibold text-slate-300">Total</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-xs text-slate-400 font-medium">
                      {fmtCurrency(distribution.reduce((s, i) => s + i.avg_monthly, 0))}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-xs font-bold text-indigo-400">
                      {fmtCurrency(distribution.reduce((s, i) => s + i.suggested_annual, 0))}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-xs font-bold text-slate-300">
                      {fmtCurrency(distribution.reduce((s, i) => s + i.suggested_monthly, 0))}
                    </td>
                    <td className="px-4 py-2.5 text-right text-xs text-slate-500">100%</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div className="flex justify-end">
              <button
                onClick={applyDistribution}
                disabled={applying}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-sm rounded-lg transition-colors"
              >
                {applying ? "Application…" : "Appliquer à tous"}
              </button>
            </div>
          </div>
        )}

        {distribution && distribution.length === 0 && (
          <p className="text-xs text-slate-500 italic">Aucune dépense trouvée sur cette période.</p>
        )}
      </div>

      {/* Créer un groupe */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Nouveau groupe</h2>
        <div className="flex items-center gap-3">
          <input
            value={newGroupName}
            onChange={e => setNewGroupName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && createGroup()}
            placeholder="Nom du groupe..."
            className="flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500"
          />
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-500">Couleur</label>
            <input type="color" value={newGroupColor} onChange={e => setNewGroupColor(e.target.value)}
              className="w-8 h-8 rounded cursor-pointer bg-transparent border-0" />
          </div>
          <button onClick={createGroup} disabled={!newGroupName.trim()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm rounded-lg transition-colors">
            Créer
          </button>
        </div>
      </div>

      {/* Récap budgets configurés */}
      {groups.some(g => g.budget_annual) && (() => {
        const totalAnnual  = groups.reduce((s, g) => s + (g.budget_annual ?? 0), 0);
        const totalMonthly = groups.reduce((s, g) => s + (g.budget_monthly ?? 0), 0);
        const configured   = groups.filter(g => g.budget_annual).length;
        return (
          <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl px-5 py-3 flex items-center justify-between flex-wrap gap-3">
            <p className="text-xs text-indigo-300">
              {configured} groupe{configured > 1 ? "s" : ""} avec budget configuré
            </p>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <p className="text-[10px] text-indigo-400/70 uppercase tracking-wide">Total annuel</p>
                <p className="text-sm font-bold text-indigo-300">{fmtCurrency(totalAnnual)}</p>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-indigo-400/70 uppercase tracking-wide">Total mensuel</p>
                <p className="text-sm font-bold text-white">{fmtCurrency(totalMonthly)}</p>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Liste des groupes */}
      <div className="space-y-3">
        {groups.map(group => (
          <div key={group.id} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {/* Header groupe */}
            <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-800">
              {editingGroup?.id === group.id ? (
                <>
                  <input type="color" value={editingGroup.color}
                    onChange={e => setEditingGroup({ ...editingGroup, color: e.target.value })}
                    className="w-7 h-7 rounded cursor-pointer bg-transparent border-0 shrink-0" />
                  <input
                    value={editingGroup.name}
                    onChange={e => setEditingGroup({ ...editingGroup, name: e.target.value })}
                    className="flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-1.5 outline-none focus:border-indigo-500"
                  />
                  <input type="number" value={editingGroup.sort_order}
                    onChange={e => setEditingGroup({ ...editingGroup, sort_order: Number(e.target.value) })}
                    className="w-16 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-2 py-1.5 outline-none text-center"
                    title="Ordre d'affichage" />
                  <button onClick={() => saveGroup(editingGroup)}
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg">
                    Enregistrer
                  </button>
                  <button onClick={() => setEditingGroup(null)} className="text-slate-500 hover:text-slate-300 text-sm">✕</button>
                </>
              ) : (
                <>
                  <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: group.color }} />
                  <span className="font-semibold text-slate-200 flex-1">{group.name}</span>
                  <span className="text-xs text-slate-500">{group.categories.length} catégorie(s)</span>
                  <button onClick={() => setEditingGroup({ ...group })}
                    className="text-xs px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors">
                    Modifier
                  </button>
                  <button onClick={() => deleteGroup(group.id)}
                    className="text-xs px-2.5 py-1 rounded-lg border border-red-500/20 bg-red-500/5 text-red-400 hover:bg-red-500/10 transition-colors">
                    Supprimer
                  </button>
                </>
              )}
            </div>

            {/* Budget annuel */}
            <div className="px-5 py-3 border-b border-slate-800 bg-slate-950/30 space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500 shrink-0">Budget annuel</span>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    placeholder="Pas de budget"
                    value={limitInputs[group.id] ?? ""}
                    onChange={e => setLimitInputs(prev => ({ ...prev, [group.id]: e.target.value }))}
                    onKeyDown={e => e.key === "Enter" && saveBudgetLimit(group.id)}
                    className="w-28 bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 outline-none focus:border-indigo-500 tabular-nums"
                  />
                  <span className="text-xs text-slate-600">€ / an</span>
                  <button
                    onClick={() => saveBudgetLimit(group.id)}
                    disabled={savingLimit === group.id}
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs rounded-lg transition-colors"
                  >
                    {savingLimit === group.id ? "…" : "Enregistrer"}
                  </button>
                  {group.budget_annual && (
                    <button
                      onClick={() => { setLimitInputs(prev => ({ ...prev, [group.id]: "" })); saveBudgetLimit(group.id); }}
                      className="text-xs text-slate-600 hover:text-red-400 transition-colors"
                    >
                      Supprimer
                    </button>
                  )}
                </div>
                {group.budget_annual && (
                  <span className="ml-auto text-xs text-slate-500">
                    = <span className="text-indigo-400 font-medium">{fmtCurrency(group.budget_annual / 12)}/mois</span>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500 shrink-0">Projection</span>
                <select
                  value={group.projection_mode}
                  onChange={e => saveProjectionMode(group.id, e.target.value as ProjectionMode)}
                  className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 outline-none focus:border-indigo-500"
                >
                  {(Object.keys(PROJECTION_MODE_LABELS) as ProjectionMode[]).map(mode => (
                    <option key={mode} value={mode}>{PROJECTION_MODE_LABELS[mode]}</option>
                  ))}
                </select>
                <span className="text-[10px] text-slate-600">
                  {group.projection_mode === "linear" && "Pour les dépenses réparties au fil du mois."}
                  {group.projection_mode === "fixed_historical" && "Pour les charges payées une fois, estimées avant paiement."}
                  {group.projection_mode === "actual_only" && "Pour les dépenses ponctuelles sans extrapolation."}
                </span>
              </div>
            </div>

            {/* Catégories du groupe */}
            <div className="px-5 py-3 flex flex-wrap gap-2">
              {group.categories.map(cat => (
                <div key={cat.id} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: cat.color }} />
                  <span className="text-xs text-slate-300">{cat.name}</span>
                  <button
                    onClick={() => setMovingCat({ cat, fromGroupId: group.id })}
                    className="text-slate-600 hover:text-slate-300 text-xs ml-0.5"
                    title="Déplacer vers un autre groupe"
                  >⇄</button>
                  <button
                    onClick={() => unassignCategory(cat.id)}
                    className="text-slate-600 hover:text-red-400 text-xs"
                    title="Retirer du groupe"
                  >✕</button>
                </div>
              ))}
              {group.categories.length === 0 && (
                <p className="text-xs text-slate-600 italic">Aucune catégorie</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Catégories non assignées */}
      {unassigned.length > 0 && (
        <div className="bg-slate-900 border border-amber-500/20 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-amber-400 mb-3">Catégories sans groupe ({unassigned.length})</h2>
          <div className="flex flex-wrap gap-2">
            {unassigned.map(cat => (
              <div key={cat.id} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800 border border-amber-500/20">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: cat.color }} />
                <span className="text-xs text-slate-300">{cat.name}</span>
                <select
                  defaultValue=""
                  onChange={e => e.target.value && moveCategory(cat.id, Number(e.target.value))}
                  className="text-[10px] bg-transparent text-slate-500 outline-none cursor-pointer"
                >
                  <option value="">→ groupe</option>
                  {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modal déplacement */}
      {movingCat && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-80 space-y-4">
            <p className="text-sm text-slate-300">
              Déplacer <span className="font-semibold text-white">{movingCat.cat.name}</span> vers :
            </p>
            <div className="space-y-2">
              {groups.filter(g => g.id !== movingCat.fromGroupId).map(g => (
                <button key={g.id} onClick={() => moveCategory(movingCat.cat.id, g.id)}
                  className="w-full text-left px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm text-slate-300 transition-colors flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: g.color }} />
                  {g.name}
                </button>
              ))}
            </div>
            <button onClick={() => setMovingCat(null)} className="w-full text-xs text-slate-500 hover:text-slate-300">Annuler</button>
          </div>
        </div>
      )}

      {toastMsg && (
        <div className="fixed bottom-6 right-6 bg-emerald-600 text-white text-sm px-4 py-3 rounded-xl shadow-lg">
          {toastMsg}
        </div>
      )}
    </div>
  );
}
