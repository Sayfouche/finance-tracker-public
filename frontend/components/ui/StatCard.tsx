"use client";
import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string;
  sub?: string;
  icon: LucideIcon;
  color?: "indigo" | "green" | "red" | "amber" | "slate";
  trend?: number;
  index?: number;
  onClick?: () => void;
}

const colors = {
  indigo: "bg-indigo-500/10 border-indigo-500/20 text-indigo-400",
  green:  "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
  red:    "bg-red-500/10 border-red-500/20 text-red-400",
  amber:  "bg-amber-500/10 border-amber-500/20 text-amber-400",
  slate:  "bg-slate-500/10 border-slate-500/20 text-slate-400",
};

export default function StatCard({ label, value, sub, icon: Icon, color = "indigo", trend, index = 0, onClick }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.07 }}
      onClick={onClick}
      className={`bg-slate-900 border border-slate-800 rounded-xl p-5 ${onClick ? "cursor-pointer hover:border-slate-600 transition-colors" : ""}`}
    >
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-slate-400">{label}</p>
        <div className={`p-1.5 rounded-lg border ${colors[color]}`}>
          <Icon size={14} />
        </div>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
      {trend !== undefined && (
        <p className={`text-xs mt-1 font-medium ${trend >= 0 ? "text-emerald-400" : "text-red-400"}`}>
          {trend >= 0 ? "+" : ""}{trend.toFixed(1)}% vs mois dernier
        </p>
      )}
    </motion.div>
  );
}
