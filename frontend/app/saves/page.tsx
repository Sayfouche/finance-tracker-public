import { Cloud, Download, Plus } from "lucide-react";

const saves = [
  { name: "Bilan avril 2026",        desc: "Snapshot demo mensuel",      date: "2026-04-30", size: "42 Ko" },
  { name: "Patrimoine mars 2026",    desc: "Données demo consolidées",   date: "2026-03-31", size: "39 Ko" },
  { name: "Bilan janvier 2026",      desc: "Point de départ demo",       date: "2026-01-31", size: "38 Ko" },
];

export default function SavesPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Cloud Saves</h1>
          <p className="text-sm text-slate-500 mt-0.5">Points de sauvegarde stockés sur GitHub</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors">
          <Plus size={14} />
          Nouveau save
        </button>
      </div>

      {/* Info */}
      <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-4 flex items-start gap-3">
        <Cloud size={16} className="text-indigo-400 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-sm text-indigo-300 font-medium">Stockage GitHub gratuit</p>
          <p className="text-xs text-slate-400 mt-0.5">
            Chaque save est un commit sur votre repo privé <code className="text-indigo-300">finance-tracker-saves</code>.
            Restaurez n&apos;importe quel état en un clic.
          </p>
        </div>
      </div>

      {/* Liste saves */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        {saves.map((save, i) => (
          <div key={i} className="flex items-center justify-between px-5 py-4 border-b border-slate-800/60 last:border-0 hover:bg-slate-800/30 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                <Cloud size={13} className="text-indigo-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-white">{save.name}</p>
                <p className="text-xs text-slate-500">{save.desc} · {save.date} · {save.size}</p>
              </div>
            </div>
            <button className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg transition-colors border border-slate-700">
              <Download size={12} />
              Restaurer
            </button>
          </div>
        ))}
      </div>

      <p className="text-xs text-slate-600 text-center">
        Fonctionnalité à connecter à l&apos;API GitHub — Phase 4
      </p>
    </div>
  );
}
