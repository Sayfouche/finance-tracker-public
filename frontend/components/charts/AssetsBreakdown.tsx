"use client";
import { useState, useEffect } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface AssetGroup {
  name: string;
  value: number;
  color: string;
}

const fmt = (v: number) =>
  v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export default function AssetsBreakdown({ actifs }: { actifs: AssetGroup[] }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="h-[220px]" />;

  const data = actifs.length > 0 ? actifs : [{ name: "Aucune donnée", value: 1, color: "#334155" }];

  return (
    <div>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={85}
            paddingAngle={2}
            dataKey="value"
            nameKey="name"
          >
            {data.map((entry, i) => <Cell key={i} fill={entry.color} />)}
          </Pie>
          <Tooltip
            formatter={(v) => [fmt(Number(v)), ""]}
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
          />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(v) => <span style={{ color: "#94a3b8", fontSize: 11 }}>{v}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
