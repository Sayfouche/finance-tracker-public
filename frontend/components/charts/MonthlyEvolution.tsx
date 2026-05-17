"use client";
import { useState, useEffect } from "react";
import {
  ComposedChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Line,
} from "recharts";

interface MonthPoint {
  label: string;
  revenus: number;
  depenses: number;
  epargne: number;
}

const fmt = (v: number) => `${(v / 1000).toFixed(1)}k€`;

export default function MonthlyEvolution({ history }: { history: MonthPoint[] }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-[300px]" />;
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-4">Évolution sur 12 mois</h3>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={history} barGap={2}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={fmt} tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip
            formatter={(v, name) => [`${Number(v).toLocaleString("fr-FR")} €`, String(name)]}
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Legend formatter={(v) => <span style={{ color: "#94a3b8", fontSize: 11 }}>{v}</span>} />
          <Bar dataKey="revenus"  name="Revenus"  fill="#6366f1" opacity={0.7} radius={[3, 3, 0, 0]} />
          <Bar dataKey="depenses" name="Dépenses" fill="#ef4444" opacity={0.7} radius={[3, 3, 0, 0]} />
          <Line dataKey="epargne" name="Épargne" stroke="#22c55e" strokeWidth={2} dot={false} type="monotone" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
