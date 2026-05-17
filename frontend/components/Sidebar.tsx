"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, CreditCard, TrendingUp, Upload, Cloud, Settings, List, Bot, Calculator
} from "lucide-react";

const nav = [
  { href: "/",              label: "Budget",       icon: LayoutDashboard },
  { href: "/transactions",  label: "Transactions", icon: List },
  { href: "/accounts",      label: "Comptes",      icon: CreditCard },
  { href: "/patrimony",     label: "Patrimoine",   icon: TrendingUp },
  { href: "/simulator",     label: "Simulateur",   icon: Calculator },
  { href: "/agents",        label: "Agents",       icon: Bot },
  { href: "/import",        label: "Import",       icon: Upload },
  { href: "/saves",         label: "Saves",        icon: Cloud },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center">
            <TrendingUp size={14} className="text-indigo-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-white leading-none">Finance</p>
            <p className="text-[10px] text-slate-500 leading-none mt-0.5">Tracker</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                active
                  ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/25"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-slate-800">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all"
        >
          <Settings size={16} />
          Paramètres
        </Link>
      </div>
    </aside>
  );
}
