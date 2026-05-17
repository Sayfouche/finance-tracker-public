import { getAccounts } from "@/lib/api";
import ImportForm from "@/components/ImportForm";

export default async function ImportPage() {
  const accounts = await getAccounts();
  const courants = accounts.filter(a => ["courant", "epargne", "livret"].includes(a.type));

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Import des relevés</h1>
        <p className="text-sm text-slate-500 mt-0.5">Importez vos relevés bancaires CSV ou Excel</p>
      </div>
      <ImportForm accounts={courants} />
    </div>
  );
}
