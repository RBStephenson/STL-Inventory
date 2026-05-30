import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Users, Zap, X } from "lucide-react";
import { api, Creator } from "../api/client";
import StorefrontEnrich from "../components/StorefrontEnrich";

export default function Creators() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [enriching, setEnriching] = useState<Creator | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => { api.models.creators().then(setCreators).catch(() => {}); }, []);

  const filtered = search
    ? creators.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()))
    : creators;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Users size={20} className="text-indigo-400" />
          <h1 className="text-2xl font-bold text-gray-100">Creators</h1>
          <span className="text-sm text-gray-500 ml-1">({creators.length})</span>
        </div>
        <input
          type="text"
          placeholder="Search creators…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500 w-48"
        />
      </div>

      {/* Storefront enrich panel */}
      {enriching && (
        <div className="mb-6">
          <StorefrontEnrich
            creatorId={enriching.id}
            creatorName={enriching.name}
            onDone={() => setEnriching(null)}
          />
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {filtered.map((c) => (
          <div
            key={c.id}
            className={`group bg-gray-900 border rounded-lg p-4 flex flex-col gap-2 transition-colors ${
              enriching?.id === c.id ? "border-indigo-500" : "border-gray-800 hover:border-gray-700"
            }`}
          >
            <Link
              to={`/?creator_id=${c.id}`}
              className="font-medium text-gray-100 truncate hover:text-indigo-300 transition-colors"
              title={c.name}
            >
              {c.name}
            </Link>
            <p className="text-xs text-gray-500">{c.model_count} models</p>
            <button
              onClick={() => setEnriching(enriching?.id === c.id ? null : c)}
              className="flex items-center gap-1 text-xs text-gray-600 hover:text-indigo-400 transition-colors mt-auto pt-1 border-t border-gray-800"
            >
              {enriching?.id === c.id
                ? <><X size={11} /> Close</>
                : <><Zap size={11} /> Enrich from web</>
              }
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
