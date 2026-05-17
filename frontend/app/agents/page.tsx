"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, FileJson, GitCompareArrows, Loader2, Play, ScrollText } from "lucide-react";

import { API_BASE } from "@/lib/config";

const fmtDate = (value: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const fmtMoney = (value: number, currency = "EUR") =>
  value.toLocaleString("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  });

interface AgentRun {
  run_id: string;
  provider: string;
  snapshot_path: string;
  snapshot_date: string;
  accounts_count: number;
  transactions_count: number;
  errors_count: number;
  date_from: string | null;
  date_to: string | null;
}

interface DiffMatch {
  id: number;
  date: string;
  label: string;
  amount: number;
  type: string;
}

interface DiffItem {
  item_id: string;
  status: "new" | "duplicate_candidate" | "already_imported" | "unmapped_account" | "error";
  provider_account_id: string;
  local_account_id: number | null;
  transaction: {
    date: string;
    label: string;
    amount: number;
    currency?: string;
    external_id?: string;
  };
  matches: DiffMatch[];
  decision: "imported" | "ignored" | null;
}

interface RunDiff {
  run_id: string;
  provider: string;
  summary: {
    new: number;
    duplicate_candidate: number;
    already_imported: number;
    unmapped_account: number;
    error: number;
  };
  items: DiffItem[];
}

const statusMeta = {
  new: {
    label: "Nouveau",
    className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/25",
    icon: CheckCircle2,
  },
  duplicate_candidate: {
    label: "Doublon probable",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/25",
    icon: GitCompareArrows,
  },
  already_imported: {
    label: "Déjà importé",
    className: "bg-slate-700/50 text-slate-300 border-slate-600/40",
    icon: CheckCircle2,
  },
  unmapped_account: {
    label: "Compte non mappé",
    className: "bg-red-500/15 text-red-300 border-red-500/25",
    icon: AlertTriangle,
  },
  error: {
    label: "Erreur",
    className: "bg-red-500/15 text-red-300 border-red-500/25",
    icon: AlertTriangle,
  },
};

export default function AgentsPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [statusFilter, setStatusFilter] = useState<DiffItem["status"] | "all">("all");
  const [decisionFilter, setDecisionFilter] = useState<"all" | "pending" | "ignored" | "imported">("pending");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState<"import" | "ignore" | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [collecting, setCollecting] = useState(false);
  const [collectError, setCollectError] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const collectPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/agents/account-collector/runs`)
      .then((response) => response.json())
      .then((data: AgentRun[]) => {
        setRuns(data);
        if (data.length > 0) setSelectedRunId(data[0].run_id);
        setLoadingRuns(false);
      })
      .catch(() => setLoadingRuns(false));
  }, []);

  useEffect(() => {
    if (!selectedRunId) return;
    setLoadingDiff(true);
    fetch(`${API_BASE}/agents/account-collector/runs/${encodeURIComponent(selectedRunId)}/diff`)
      .then((response) => response.json())
      .then((data: RunDiff) => {
        setDiff(data);
        setStatusFilter("all");
        setDecisionFilter("pending");
        setSelectedItems(new Set());
        setLoadingDiff(false);
      })
      .catch(() => setLoadingDiff(false));
  }, [selectedRunId]);

  const selectedRun = runs.find((run) => run.run_id === selectedRunId) ?? null;
  const filteredItems = useMemo(() => {
    if (!diff) return [];
    return diff.items.filter((item) => {
      const statusMatch = statusFilter === "all" || item.status === statusFilter;
      const decisionMatch =
        decisionFilter === "all" ||
        (decisionFilter === "pending" && item.decision === null && item.status !== "already_imported") ||
        item.decision === decisionFilter;
      return statusMatch && decisionMatch;
    });
  }, [diff, statusFilter, decisionFilter]);
  const selectedList = Array.from(selectedItems);
  const selectedRows = useMemo(
    () => diff?.items.filter((item) => selectedItems.has(item.item_id)) ?? [],
    [diff, selectedItems]
  );
  const importableVisible = filteredItems.filter((item) => item.status === "new" && item.decision === null);
  const selectedImportableCount = filteredItems.filter((item) => selectedItems.has(item.item_id) && item.status === "new" && item.decision === null).length;
  const selectedImpact = useMemo(() => buildImpact(selectedRows), [selectedRows]);

  function toggleItem(itemId: string) {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }

  function selectVisibleNew() {
    setSelectedItems(new Set(importableVisible.map((item) => item.item_id)));
  }

  async function applyDecision(decision: "import" | "ignore") {
    if (!selectedRunId || selectedList.length === 0) return;
    setActionLoading(decision);
    setActionMessage(null);
    try {
      const response = await fetch(`${API_BASE}/agents/account-collector/runs/${encodeURIComponent(selectedRunId)}/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_ids: selectedList, decision }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message ?? data.detail ?? "Action impossible");
      setActionMessage(
        decision === "import"
          ? `${data.imported.length} transaction(s) importée(s), ${data.skipped.length} ignorée(s) par garde-fou.`
          : `${data.ignored.length} ligne(s) marquée(s) ignorée(s).`
      );
      setSelectedItems(new Set());
      const refreshed = await fetch(`${API_BASE}/agents/account-collector/runs/${encodeURIComponent(selectedRunId)}/diff`).then((res) => res.json());
      setDiff(refreshed);
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : "Action impossible");
    } finally {
      setActionLoading(null);
    }
  }

  async function triggerCollect() {
    setCollecting(true);
    setCollectError(null);
    try {
      const res = await fetch(`${API_BASE}/agents/account-collector/collect`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail ?? "Erreur au démarrage");
      }
      // Poll every 4s for up to 90s — stop when a new run appears
      const initialCount = runs.length;
      let elapsed = 0;
      collectPollRef.current = setInterval(async () => {
        elapsed += 4;
        const fresh = await fetch(`${API_BASE}/agents/account-collector/runs`).then(r => r.json()) as AgentRun[];
        if (fresh.length > initialCount || elapsed >= 90) {
          clearInterval(collectPollRef.current!);
          setCollecting(false);
          setRuns(fresh);
          if (fresh.length > 0) setSelectedRunId(fresh[0].run_id);
        }
      }, 4000);
    } catch (e) {
      setCollecting(false);
      setCollectError(e instanceof Error ? e.message : "Erreur inconnue");
    }
  }

  async function fetchLogs() {
    setLoadingLogs(true);
    try {
      const data = await fetch(`${API_BASE}/agents/account-collector/logs?lines=150`).then(r => r.json());
      setLogLines(data.lines ?? []);
    } finally {
      setLoadingLogs(false);
      setTimeout(() => logEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  function toggleLogs() {
    if (!showLogs) fetchLogs();
    setShowLogs(s => !s);
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Bot className="text-indigo-400" size={24} />
            Agent Account Collector
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Staging des outputs générés par l’agent, avec validation manuelle avant intégration.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleLogs}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs transition-colors ${
              showLogs ? "bg-slate-700 border-slate-600 text-white" : "border-slate-700 text-slate-400 hover:text-slate-200"
            }`}
          >
            <ScrollText size={14} />
            Logs
          </button>
          <button
            onClick={triggerCollect}
            disabled={collecting}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-xs font-semibold text-white transition-colors"
          >
            {collecting ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {collecting ? "Collecte en cours…" : "Lancer collecte"}
          </button>
          <select
            value={selectedRunId}
            onChange={(event) => setSelectedRunId(event.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none min-w-72"
          >
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.provider} · {run.run_id}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loadingRuns && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500 text-sm">
          Chargement des runs agent...
        </div>
      )}

      {!loadingRuns && runs.length === 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
          <FileJson className="mx-auto text-slate-600 mb-3" size={28} />
          <p className="text-slate-300 font-medium">Aucun output agent trouvé</p>
          <p className="text-slate-500 text-sm mt-1">
            Lance une collecte pour produire un snapshot JSON dans le dossier agent.
          </p>
        </div>
      )}

      {collectError && (
        <div className="bg-red-500/10 border border-red-500/25 rounded-xl px-4 py-3 text-sm text-red-300">
          {collectError}
        </div>
      )}

      {showLogs && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
            <p className="text-xs font-semibold text-slate-400">collect_powens.log</p>
            <button onClick={fetchLogs} disabled={loadingLogs} className="text-xs text-slate-500 hover:text-slate-300 disabled:opacity-40">
              {loadingLogs ? "Chargement…" : "Rafraîchir"}
            </button>
          </div>
          <div className="p-4 h-64 overflow-y-auto font-mono text-[11px] leading-relaxed">
            {logLines.length === 0 ? (
              <p className="text-slate-600">Aucun log pour le moment.</p>
            ) : (
              logLines.map((line, i) => (
                <p
                  key={i}
                  className={
                    line.includes("ERREUR") ? "text-red-400" :
                    line.includes("terminé") ? "text-emerald-400" :
                    line.includes("démarré") ? "text-indigo-400" :
                    "text-slate-400"
                  }
                >
                  {line}
                </p>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {selectedRun && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <Stat label="Provider" value={selectedRun.provider} />
          <Stat label="Comptes" value={String(selectedRun.accounts_count)} />
          <Stat label="Transactions" value={String(selectedRun.transactions_count)} />
          <Stat label="Erreurs output" value={String(selectedRun.errors_count)} danger={selectedRun.errors_count > 0} />
          <Stat label="Date run" value={fmtDate(selectedRun.snapshot_date)} compact />
        </div>
      )}

      {diff && (
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
          <SummaryCard
            label="Nouvelles"
            value={diff.summary.new}
            color="emerald"
            active={statusFilter === "new"}
            onClick={() => setStatusFilter(statusFilter === "new" ? "all" : "new")}
          />
          <SummaryCard
            label="Doublons probables"
            value={diff.summary.duplicate_candidate}
            color="amber"
            active={statusFilter === "duplicate_candidate"}
            onClick={() => setStatusFilter(statusFilter === "duplicate_candidate" ? "all" : "duplicate_candidate")}
          />
          <SummaryCard
            label="Déjà importées"
            value={diff.summary.already_imported}
            color="slate"
            active={statusFilter === "already_imported"}
            onClick={() => setStatusFilter(statusFilter === "already_imported" ? "all" : "already_imported")}
          />
          <SummaryCard
            label="Comptes non mappés"
            value={diff.summary.unmapped_account}
            color="red"
            active={statusFilter === "unmapped_account"}
            onClick={() => setStatusFilter(statusFilter === "unmapped_account" ? "all" : "unmapped_account")}
          />
          <SummaryCard
            label="Ignorées"
            value={diff.items.filter((item) => item.decision === "ignored").length}
            color="slate"
            active={decisionFilter === "ignored"}
            onClick={() => setDecisionFilter(decisionFilter === "ignored" ? "pending" : "ignored")}
          />
          <SummaryCard
            label="Importées"
            value={diff.items.filter((item) => item.decision === "imported").length}
            color="slate"
            active={decisionFilter === "imported"}
            onClick={() => setDecisionFilter(decisionFilter === "imported" ? "pending" : "imported")}
          />
        </div>
      )}

      {diff && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <SegmentButton label="À traiter" active={decisionFilter === "pending"} onClick={() => setDecisionFilter("pending")} />
            <SegmentButton label="Tout" active={decisionFilter === "all"} onClick={() => setDecisionFilter("all")} />
            <SegmentButton label="Ignorés" active={decisionFilter === "ignored"} onClick={() => setDecisionFilter("ignored")} />
            <SegmentButton label="Importés" active={decisionFilter === "imported"} onClick={() => setDecisionFilter("imported")} />
          </div>
          <div className="text-xs text-slate-400">
            Sélection : <span className="font-semibold text-white">{selectedRows.length}</span>
            {" · "}Importables : <span className="font-semibold text-emerald-300">{selectedImpact.importable}</span>
            {" · "}Période : <span className="font-semibold text-slate-200">{selectedImpact.period}</span>
            {" · "}Net : <span className={selectedImpact.net >= 0 ? "font-semibold text-emerald-300" : "font-semibold text-red-300"}>
              {fmtMoney(selectedImpact.net)}
            </span>
          </div>
        </div>
      )}

      {selectedRows.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-start justify-between gap-6">
            <div>
              <h2 className="text-sm font-semibold text-white">Impact avant action</h2>
              <p className="text-xs text-slate-500 mt-1">
                L’import créera uniquement les lignes sélectionnées qui sont au statut Nouveau et pas déjà importées.
              </p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-right">
              <MiniStat label="Lignes" value={String(selectedRows.length)} />
              <MiniStat label="Importables" value={String(selectedImpact.importable)} />
              <MiniStat label="Débits" value={fmtMoney(selectedImpact.debits)} danger />
              <MiniStat label="Crédits" value={fmtMoney(selectedImpact.credits)} success />
            </div>
          </div>
          {selectedImpact.byAccount.length > 0 && (
            <div className="mt-4 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {selectedImpact.byAccount.map((account) => (
                <div key={account.key} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <p className="text-xs font-medium text-slate-200">Compte local {account.localAccountId ?? "—"}</p>
                  <p className="text-[11px] text-slate-500">
                    {account.count} ligne(s) · {account.from} → {account.to}
                  </p>
                  <p className={account.net >= 0 ? "text-xs font-semibold text-emerald-300 mt-1" : "text-xs font-semibold text-red-300 mt-1"}>
                    {fmtMoney(account.net)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Diff du run</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Les transactions déjà importées par ID provider sont exclues de la vue à traiter.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {actionMessage && <span className="text-xs text-slate-400">{actionMessage}</span>}
            <button
              onClick={selectVisibleNew}
              disabled={importableVisible.length === 0 || Boolean(actionLoading)}
              className="px-3 py-2 rounded-lg border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-40"
            >
              Sélectionner nouveaux
            </button>
            <button
              onClick={() => applyDecision("ignore")}
              disabled={selectedItems.size === 0 || Boolean(actionLoading)}
              className="px-3 py-2 rounded-lg border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-40"
            >
              {actionLoading === "ignore" ? <Loader2 className="animate-spin" size={14} /> : "Ignorer"}
            </button>
            <button
              onClick={() => applyDecision("import")}
              disabled={selectedImportableCount === 0 || Boolean(actionLoading)}
              className="px-3 py-2 rounded-lg bg-indigo-600 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              {actionLoading === "import" ? <Loader2 className="animate-spin" size={14} /> : `Importer ${selectedImportableCount}`}
            </button>
          </div>
        </div>

        {loadingDiff ? (
          <div className="text-center py-12 text-slate-500 text-sm">Analyse du diff...</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
                <th className="text-left px-5 py-3">Statut</th>
                <th className="text-left px-5 py-3">Choix</th>
                <th className="text-left px-5 py-3">Compte provider</th>
                <th className="text-left px-5 py-3">Transaction agent</th>
                <th className="text-right px-5 py-3">Montant</th>
                <th className="text-left px-5 py-3">Match existant</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.slice(0, 300).map((item) => {
                const meta = statusMeta[item.status];
                const Icon = meta.icon;
                const amount = item.transaction.amount;
                return (
                  <tr key={item.item_id} className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/30">
                    <td className="px-5 py-3">
                      <div className="space-y-1">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-xs font-medium ${meta.className}`}>
                          <Icon size={13} />
                          {meta.label}
                        </span>
                        {item.decision && (
                          <span className="block text-[10px] text-slate-500">
                            {item.decision === "imported" ? "déjà importée" : "ignorée"}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <input
                        type="checkbox"
                        checked={selectedItems.has(item.item_id)}
                        onChange={() => toggleItem(item.item_id)}
                        disabled={item.decision === "imported" || item.status === "already_imported"}
                        className="h-4 w-4 rounded border-slate-600 bg-slate-900 accent-indigo-500 disabled:opacity-30"
                        aria-label="Sélectionner la ligne"
                      />
                    </td>
                    <td className="px-5 py-3">
                      <p className="text-slate-200 font-medium">#{item.provider_account_id}</p>
                      <p className="text-xs text-slate-500">local {item.local_account_id ?? "—"}</p>
                    </td>
                    <td className="px-5 py-3 max-w-md">
                      <p className="text-slate-200 truncate">{item.transaction.label}</p>
                      <p className="text-xs text-slate-500">
                        {item.transaction.date}
                        {item.transaction.external_id ? ` · ext ${item.transaction.external_id}` : ""}
                      </p>
                    </td>
                    <td className={`px-5 py-3 text-right font-semibold ${amount >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {fmtMoney(amount, item.transaction.currency ?? "EUR")}
                    </td>
                    <td className="px-5 py-3">
                      {item.matches.length === 0 ? (
                        <span className="text-slate-600">—</span>
                      ) : (
                        <div className="space-y-1">
                          {item.matches.slice(0, 2).map((match) => (
                            <div key={match.id}>
                              <p className="text-slate-300 truncate max-w-xs">#{match.id} · {match.label}</p>
                              <p className="text-xs text-slate-500">{match.date} · {fmtMoney(match.amount)}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!loadingDiff && filteredItems.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-slate-500">
                    Aucun élément pour ce filtre.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {filteredItems.length > 300 && (
        <p className="text-xs text-slate-500 text-center">
          Affichage limité aux 300 premières lignes pour garder l’écran rapide.
        </p>
      )}
    </div>
  );
}

function Stat({ label, value, danger = false, compact = false }: { label: string; value: string; danger?: boolean; compact?: boolean }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`font-semibold ${compact ? "text-sm" : "text-lg"} ${danger ? "text-red-400" : "text-white"}`}>
        {value}
      </p>
    </div>
  );
}

function SegmentButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-3 py-2 text-xs transition-colors ${
        active
          ? "bg-indigo-600 text-white"
          : "border border-slate-800 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
      }`}
    >
      {label}
    </button>
  );
}

function MiniStat({
  label,
  value,
  danger = false,
  success = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
  success?: boolean;
}) {
  const color = danger ? "text-red-300" : success ? "text-emerald-300" : "text-white";
  return (
    <div>
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={`text-sm font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function buildImpact(items: DiffItem[]) {
  const importableRows = items.filter((item) => item.status === "new" && item.decision === null);
  const dates = importableRows.map((item) => item.transaction.date.slice(0, 10)).sort();
  const credits = importableRows
    .filter((item) => item.transaction.amount > 0)
    .reduce((sum, item) => sum + item.transaction.amount, 0);
  const debits = importableRows
    .filter((item) => item.transaction.amount < 0)
    .reduce((sum, item) => sum + Math.abs(item.transaction.amount), 0);
  const byAccountMap = new Map<string, {
    key: string;
    localAccountId: number | null;
    count: number;
    from: string;
    to: string;
    net: number;
  }>();

  for (const item of importableRows) {
    const key = `${item.provider_account_id}-${item.local_account_id ?? "none"}`;
    const day = item.transaction.date.slice(0, 10);
    const existing = byAccountMap.get(key);
    if (!existing) {
      byAccountMap.set(key, {
        key,
        localAccountId: item.local_account_id,
        count: 1,
        from: day,
        to: day,
        net: item.transaction.amount,
      });
    } else {
      existing.count += 1;
      existing.from = day < existing.from ? day : existing.from;
      existing.to = day > existing.to ? day : existing.to;
      existing.net += item.transaction.amount;
    }
  }

  return {
    importable: importableRows.length,
    credits,
    debits,
    net: credits - debits,
    period: dates.length ? `${dates[0]} → ${dates[dates.length - 1]}` : "—",
    byAccount: Array.from(byAccountMap.values()).sort((a, b) => b.count - a.count),
  };
}

function SummaryCard({
  label,
  value,
  color,
  active,
  onClick,
}: {
  label: string;
  value: number;
  color: "emerald" | "amber" | "red" | "slate";
  active: boolean;
  onClick: () => void;
}) {
  const colors = {
    emerald: "text-emerald-400 border-emerald-500/25",
    amber: "text-amber-400 border-amber-500/25",
    red: "text-red-400 border-red-500/25",
    slate: "text-slate-300 border-slate-700",
  };
  return (
    <button
      onClick={onClick}
      className={`text-left bg-slate-900 border rounded-xl p-4 transition-colors hover:bg-slate-800/70 ${active ? colors[color] : "border-slate-800"}`}
    >
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colors[color].split(" ")[0]}`}>{value}</p>
    </button>
  );
}
