"use client";
import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/config";
import {
  futureValue,
  yearsToTarget,
  yearsAgo,
  capitalVsContribCrossover,
  fmtYears,
} from "@/lib/simulator";
import GrowthCurveChart from "@/components/simulator/GrowthCurveChart";
import MilestonesChart from "@/components/simulator/MilestonesChart";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AvailableAccount {
  id: number;
  name: string;
  type: string;
  balance: number;
}

interface ApiConfig {
  monthly_contribution: number;
  annual_rate: number;
  account_types: string[];
  milestone_step: number;
  milestone_max: number;
  starting_capital: number;
  available_accounts: AvailableAccount[];
}

const STEP_OPTIONS = [25000, 50000, 100000, 200000, 250000];

function generateMilestones(step: number, max: number): number[] {
  const result: number[] = [];
  let v = step;
  while (v < max) { result.push(v); v += step; }
  result.push(max);
  return result;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const MILESTONE_COLORS = ["#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#ec4899", "#f43f5e"];

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  pea: "PEA",
  cto: "CTO",
  per: "PER",
  assurance_vie: "Assurance-vie",
  livret: "Livret",
  epargne: "Épargne",
  courant: "Compte courant",
  immobilier: "Immobilier",
  autre_actif: "Autre actif",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const fmt = (n: number) => Math.round(n).toLocaleString("fr-FR");

// ─── Block 1: La moitié du chemin ─────────────────────────────────────────────

function HalfwayBlock({
  capital,
  monthly,
  rate,
  milestones,
}: {
  capital: number;
  monthly: number;
  rate: number;
  milestones: number[];
}) {
  const finalGoal = milestones[milestones.length - 1];
  if (!finalGoal) return null;

  const monthlyRate = rate / 100 / 12;
  const totalYears = yearsToTarget(capital, rate, monthly, finalGoal);

  const unreachable = totalYears === null;
  const alreadyDone = capital >= finalGoal;

  const halfYears = totalYears ? totalYears / 2 : null;
  const halfCapital =
    halfYears != null
      ? futureValue(capital, monthlyRate, halfYears * 12, monthly)
      : null;

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <span className="text-[10px] font-bold text-slate-500 tracking-widest">1.</span>
        <h2 className="text-xs font-bold text-slate-300 tracking-widest uppercase">
          Calculer la moitié du chemin en investissement
        </h2>
      </div>

      {alreadyDone ? (
        <p className="text-emerald-400 text-sm">
          Objectif de {fmt(finalGoal)} € déjà atteint — félicitations !
        </p>
      ) : unreachable ? (
        <p className="text-slate-400 text-sm">
          Objectif non atteignable dans 100 ans avec ces paramètres.
        </p>
      ) : (
        <>
          {/* Subtitle */}
          <div className="text-center mb-2">
            <span className="text-2xl font-bold text-amber-400">
              {fmt(halfCapital!)} €
            </span>
            <span className="text-slate-400 text-sm ml-2">
              = la moitié du chemin vers {fmt(finalGoal)} €
            </span>
          </div>
          <p className="text-center text-[10px] text-slate-500 mb-4 tracking-wider uppercase">
            DCA {fmt(monthly)} €/mois · {rate.toFixed(1)} %/an · intérêts composés
          </p>

          {/* Chart */}
          <GrowthCurveChart
            capital={capital}
            monthly={monthly}
            annualRate={rate}
            halfYears={halfYears!}
            totalYears={totalYears!}
            halfCapital={halfCapital!}
            finalGoal={finalGoal}
          />

          {/* Stat cards */}
          <div className="grid grid-cols-2 gap-3 mt-4">
            <div className="bg-blue-950/40 border border-blue-800/40 rounded-lg p-3">
              <p className="text-[10px] font-bold text-blue-500 tracking-widest uppercase mb-1">
                Première moitié
              </p>
              <p className="text-sm font-semibold text-white">
                0 → {fmt(halfCapital!)} €
              </p>
              <p className="text-xl font-bold text-blue-400 mt-0.5">
                {fmtYears(halfYears!)}
              </p>
            </div>
            <div className="bg-emerald-950/40 border border-emerald-800/40 rounded-lg p-3">
              <p className="text-[10px] font-bold text-emerald-500 tracking-widest uppercase mb-1">
                Deuxième moitié
              </p>
              <p className="text-sm font-semibold text-white">
                {fmt(halfCapital!)} → {fmt(finalGoal)} €
              </p>
              <p className="text-xl font-bold text-emerald-400 mt-0.5">
                {fmtYears(totalYears! - halfYears!)}
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}


// ─── Block 2: Milestones timeline ─────────────────────────────────────────────

function MilestonesTimeline({
  capital,
  monthly,
  rate,
  milestones,
}: {
  capital: number;
  monthly: number;
  rate: number;
  milestones: number[];
}) {
  if (milestones.length === 0) return null;

  const allPoints = milestones.map((target, i) => ({
    target,
    // Negative for already-reached milestones (years in the past), positive for upcoming
    years: capital >= target
      ? yearsAgo(target, capital, rate, monthly)
      : yearsToTarget(capital, rate, monthly, target) ?? 0,
    color: MILESTONE_COLORS[i % MILESTONE_COLORS.length],
    reached: capital >= target,
  }));

  const upcoming = allPoints.filter((p) => !p.reached);
  const finalGoal = milestones[milestones.length - 1];
  const totalYears = upcoming[upcoming.length - 1]?.years ?? allPoints[allPoints.length - 1]?.years ?? 0;
  const allReached = upcoming.length === 0;

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] font-bold text-slate-500 tracking-widest">2.</span>
        <h2 className="text-xs font-bold text-slate-300 tracking-widest uppercase">
          Le chemin vers {fmt(finalGoal)} €
        </h2>
      </div>
      <p className="text-[10px] text-slate-500 mb-4 tracking-wider uppercase">
        DCA {fmt(monthly)} €/mois · {rate.toFixed(1)} %/an · intérêts composés
      </p>

      {allReached ? (
        <p className="text-emerald-400 text-sm">
          Objectif de {fmt(finalGoal)} € déjà atteint — félicitations !
        </p>
      ) : (
        <>
          <MilestonesChart
            capital={capital}
            monthly={monthly}
            annualRate={rate}
            milestonePoints={allPoints}
            totalYears={totalYears}
            finalGoal={finalGoal}
          />

          {/* Milestone chips */}
          <div className="flex flex-wrap gap-2 mt-4">
            {allPoints.map((p) =>
              p.reached ? (
                <div
                  key={p.target}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-700 bg-slate-700/30"
                >
                  <span className="text-emerald-500 text-xs">✓</span>
                  <span className="text-xs text-slate-500">{fmt(p.target)} €</span>
                </div>
              ) : (
                <div
                  key={p.target}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border"
                  style={{ borderColor: p.color + "55", backgroundColor: p.color + "11" }}
                >
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
                  <span className="text-xs font-semibold" style={{ color: p.color }}>
                    {fmt(p.target)} €
                  </span>
                  <span className="text-xs text-slate-400">{fmtYears(p.years)}</span>
                </div>
              )
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Block 3: Capital vs contributions ────────────────────────────────────────

function CapitalVsContribBlock({
  capital,
  monthly,
  rate,
}: {
  capital: number;
  monthly: number;
  rate: number;
}) {
  const result = capitalVsContribCrossover(capital, rate, monthly);

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <span className="text-[10px] font-bold text-slate-500 tracking-widest">3.</span>
        <h2 className="text-xs font-bold text-slate-300 tracking-widest uppercase">
          Ton argent travaille-t-il plus que toi ?
        </h2>
      </div>

      {result === null ? (
        <p className="text-slate-400 text-sm">
          Le capital ne génère jamais plus que tes versements dans 100 ans.
          Essaie d&apos;augmenter le taux de rendement.
        </p>
      ) : (
        <>
          <div className="flex items-baseline gap-2 mb-6">
            <span className="text-slate-400 text-sm">À partir de l&apos;année</span>
            <span className="text-4xl font-bold text-indigo-400">{result.year}</span>
            <span className="text-slate-400 text-sm">
              ton capital génère plus que tes versements
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-700/50 border border-slate-600 rounded-lg p-4">
              <p className="text-[10px] font-bold text-slate-500 tracking-widest uppercase mb-1">
                Versements de l&apos;année
              </p>
              <p className="text-2xl font-bold text-slate-200">
                {fmt(result.annualContribs)} €
              </p>
            </div>
            <div className="bg-emerald-950/50 border border-emerald-800/50 rounded-lg p-4">
              <p className="text-[10px] font-bold text-emerald-600 tracking-widest uppercase mb-1">
                Intérêts de l&apos;année
              </p>
              <p className="text-2xl font-bold text-emerald-400">
                {fmt(result.annualInterest)} €
              </p>
            </div>
          </div>

          <p className="text-xs text-slate-500 mt-3">
            Capital total à cette date :{" "}
            <span className="text-slate-400">{fmt(result.capitalAtCrossover)} €</span>
          </p>
        </>
      )}
    </div>
  );
}

// ─── Parameters panel ─────────────────────────────────────────────────────────

function ParametersPanel({
  apiConfig,
  monthly,
  rate,
  accountTypes,
  milestoneStep,
  milestoneMax,
  onMonthlyChange,
  onRateChange,
  onAccountTypeToggle,
  onStepChange,
  onMaxChange,
  onSave,
  saving,
}: {
  apiConfig: ApiConfig;
  monthly: number;
  rate: number;
  accountTypes: string[];
  milestoneStep: number;
  milestoneMax: number;
  onMonthlyChange: (v: number) => void;
  onRateChange: (v: number) => void;
  onAccountTypeToggle: (type: string) => void;
  onStepChange: (v: number) => void;
  onMaxChange: (v: number) => void;
  onSave: () => void;
  saving: boolean;
}) {

  const groupedTypes = useMemo(() => {
    const map: Record<string, number> = {};
    for (const a of apiConfig.available_accounts) {
      map[a.type] = (map[a.type] ?? 0) + a.balance;
    }
    return Object.entries(map).map(([type, balance]) => ({ type, balance }));
  }, [apiConfig.available_accounts]);

  const capital = useMemo(
    () =>
      apiConfig.available_accounts
        .filter((a) => accountTypes.includes(a.type))
        .reduce((s, a) => s + a.balance, 0),
    [accountTypes, apiConfig.available_accounts]
  );

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 space-y-5">
      <h3 className="text-xs font-bold text-slate-300 tracking-widest uppercase">
        Vos paramètres
      </h3>

      {/* Capital */}
      <div>
        <p className="text-xs text-slate-500 mb-2">Capital de départ</p>
        <p className="text-xl font-bold text-white mb-3">{fmt(capital)} €</p>
        <div className="space-y-1.5">
          {groupedTypes.map(({ type, balance }) => (
            <label
              key={type}
              className="flex items-center gap-2 cursor-pointer group"
            >
              <input
                type="checkbox"
                checked={accountTypes.includes(type)}
                onChange={() => onAccountTypeToggle(type)}
                className="accent-indigo-500 w-3.5 h-3.5 flex-shrink-0"
              />
              <span className="text-sm text-slate-300 group-hover:text-white transition-colors">
                {ACCOUNT_TYPE_LABELS[type] ?? type}
              </span>
              <span className="text-xs text-slate-500 ml-auto">
                {fmt(balance)} €
              </span>
            </label>
          ))}
        </div>
      </div>

      <div className="border-t border-slate-700" />

      {/* Versements */}
      <div>
        <div className="flex justify-between mb-2">
          <p className="text-xs text-slate-500">Versements mensuels</p>
          <span className="text-xs font-semibold text-slate-200">
            {fmt(monthly)} €
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={5000}
          step={50}
          value={monthly}
          onChange={(e) => onMonthlyChange(Number(e.target.value))}
          className="w-full accent-indigo-500"
        />
        <div className="flex justify-between text-[10px] text-slate-600 mt-0.5">
          <span>0 €</span>
          <span>5 000 €</span>
        </div>
      </div>

      {/* Taux */}
      <div>
        <div className="flex justify-between mb-2">
          <p className="text-xs text-slate-500">Taux de rendement annuel</p>
          <span className="text-xs font-semibold text-slate-200">
            {rate.toFixed(1)} %
          </span>
        </div>
        <input
          type="range"
          min={1}
          max={15}
          step={0.5}
          value={rate}
          onChange={(e) => onRateChange(Number(e.target.value))}
          className="w-full accent-indigo-500"
        />
        <div className="flex justify-between text-[10px] text-slate-600 mt-0.5">
          <span>1 %</span>
          <span>15 %</span>
        </div>
      </div>

      <div className="border-t border-slate-700" />

      {/* Jalons */}
      <div>
        <p className="text-xs text-slate-500 mb-2">Fréquence des jalons</p>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {STEP_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => onStepChange(s)}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                milestoneStep === s
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-slate-200"
              }`}
            >
              {s >= 1000 ? `${s / 1000}k` : s}
            </button>
          ))}
        </div>

        <p className="text-xs text-slate-500 mb-2">Objectif final</p>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={milestoneMax}
            onChange={(e) => onMaxChange(Number(e.target.value))}
            step={50000}
            min={50000}
            className="flex-1 min-w-0 bg-slate-700 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
          <span className="text-slate-400 text-sm flex-shrink-0">€</span>
        </div>
      </div>

      <button
        onClick={onSave}
        disabled={saving}
        className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
      >
        {saving ? "Sauvegarde…" : "Sauvegarder"}
      </button>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SimulatorPage() {
  const [apiConfig, setApiConfig] = useState<ApiConfig | null>(null);
  const [monthly, setMonthly] = useState(500);
  const [rate, setRate] = useState(8.0);
  const [accountTypes, setAccountTypes] = useState<string[]>(["pea", "cto", "per", "assurance_vie"]);
  const [milestoneStep, setMilestoneStep] = useState(100000);
  const [milestoneMax, setMilestoneMax] = useState(1000000);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/simulator/config`)
      .then((r) => r.json())
      .then((data: ApiConfig) => {
        setApiConfig(data);
        setMonthly(data.monthly_contribution);
        setRate(data.annual_rate);
        setAccountTypes(data.account_types);
        setMilestoneStep(data.milestone_step ?? 100000);
        setMilestoneMax(data.milestone_max ?? 1000000);
      })
      .catch(console.error);
  }, []);

  const capital = useMemo(() => {
    if (!apiConfig) return 0;
    return apiConfig.available_accounts
      .filter((a) => accountTypes.includes(a.type))
      .reduce((s, a) => s + a.balance, 0);
  }, [accountTypes, apiConfig]);

  const milestones = useMemo(
    () => generateMilestones(milestoneStep, milestoneMax),
    [milestoneStep, milestoneMax]
  );

  function toggleAccountType(type: string) {
    setAccountTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/simulator/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          monthly_contribution: monthly,
          annual_rate: rate,
          account_types: accountTypes,
          milestone_step: milestoneStep,
          milestone_max: milestoneMax,
        }),
      });
    } finally {
      setSaving(false);
    }
  }

  if (!apiConfig) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
        Chargement…
      </div>
    );
  }

  return (
    <div className="p-6 min-h-full">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white">Simulateur d&apos;investissement</h1>
        <p className="text-sm text-slate-400 mt-1">
          Projection personnalisée basée sur votre patrimoine actuel
        </p>
      </div>

      {/* Grid: blocks + parameters */}
      <div className="grid gap-5" style={{ gridTemplateColumns: "1fr 288px" }}>
        {/* Left: 3 blocks */}
        <div className="space-y-5">
          <HalfwayBlock
            capital={capital}
            monthly={monthly}
            rate={rate}
            milestones={milestones}
          />
          <MilestonesTimeline
            capital={capital}
            monthly={monthly}
            rate={rate}
            milestones={milestones}
          />
          <CapitalVsContribBlock
            capital={capital}
            monthly={monthly}
            rate={rate}
          />
        </div>

        {/* Right: parameters panel (sticky) */}
        <div className="sticky top-6 self-start">
          <ParametersPanel
            apiConfig={apiConfig}
            monthly={monthly}
            rate={rate}
            accountTypes={accountTypes}
            milestoneStep={milestoneStep}
            milestoneMax={milestoneMax}
            onMonthlyChange={setMonthly}
            onRateChange={setRate}
            onAccountTypeToggle={toggleAccountType}
            onStepChange={setMilestoneStep}
            onMaxChange={setMilestoneMax}
            onSave={handleSave}
            saving={saving}
          />
        </div>
      </div>
    </div>
  );
}
