import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, SlidersHorizontal, AlertCircle } from "lucide-react";
import { api, Model, Creator, ModelStats } from "../api/client";
import ModelCard from "../components/ModelCard";
import ScanButton from "../components/ScanButton";

const SITES = ["thingiverse", "printables", "myminifactory", "cults3d", "gumroad", "thangs", "makerworld", "other"];
const PAGE_SIZE = 48;

export default function Library() {
  const [searchParams, setSearchParams] = useSearchParams();

  // All filter state lives in the URL
  const page       = Number(searchParams.get("page") ?? 1);
  const search     = searchParams.get("q") ?? "";
  const creatorId  = searchParams.get("creator_id") ?? "";
  const site       = searchParams.get("source_site") ?? "";
  const needsReview = searchParams.get("needs_review") === "1";

  const setParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value); else next.delete(key);
      if (key !== "page") next.delete("page"); // reset page on filter change
      return next;
    });
  };
  const setPage = (p: number) => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      p > 1 ? next.set("page", String(p)) : next.delete("page");
      return next;
    });
  };

  const [models, setModels] = useState<Model[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<ModelStats | null>(null);
  const [creators, setCreators] = useState<Creator[]>([]);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(!!(creatorId || site));

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number | boolean> = { page, page_size: PAGE_SIZE };
      if (search)     params.q            = search;
      if (creatorId)  params.creator_id   = creatorId;
      if (site)       params.source_site  = site;
      if (needsReview) params.needs_review = true;
      const data = await api.models.list(params);
      setModels(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, creatorId, site, needsReview]);

  useEffect(() => { fetchModels(); }, [fetchModels]);
  useEffect(() => { api.models.creators().then(setCreators).catch(() => {}); }, []);
  useEffect(() => { api.models.stats().then(setStats).catch(() => {}); }, []);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const hasFilters = !!(creatorId || site || needsReview);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Library</h1>
          <div className="flex items-center gap-3 mt-0.5">
            <p className="text-sm text-gray-500">{total.toLocaleString()} models</p>
            {stats && stats.needs_review > 0 && (
              <button
                onClick={() => setParam("needs_review", needsReview ? "" : "1")}
                className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded transition-colors ${
                  needsReview
                    ? "bg-amber-500 text-amber-950 font-medium"
                    : "bg-amber-950/50 text-amber-400 hover:bg-amber-900/50"
                }`}
              >
                <AlertCircle size={11} />
                {stats.needs_review} need review
              </button>
            )}
          </div>
        </div>
        <ScanButton />
      </div>

      {/* Search + filter bar */}
      <div className="flex gap-2 mb-4">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search models…"
            value={search}
            onChange={(e) => setParam("q", e.target.value)}
            className="w-full bg-gray-900 border border-gray-700 rounded pl-9 pr-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex items-center gap-1.5 px-3 py-2 rounded border text-sm transition-colors ${
            showFilters || hasFilters
              ? "bg-indigo-600 border-indigo-500 text-white"
              : "bg-gray-900 border-gray-700 text-gray-400 hover:text-gray-100"
          }`}
        >
          <SlidersHorizontal size={14} />
          Filters {hasFilters && !showFilters && "•"}
        </button>
      </div>

      {showFilters && (
        <div className="flex flex-wrap gap-3 mb-4 p-3 bg-gray-900 rounded border border-gray-800">
          <select
            value={creatorId}
            onChange={(e) => setParam("creator_id", e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Creators</option>
            {creators.map((c) => (
              <option key={c.id} value={c.id}>{c.name} ({c.model_count})</option>
            ))}
          </select>
          <select
            value={site}
            onChange={(e) => setParam("source_site", e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Sites</option>
            {SITES.map((s) => (
              <option key={s} value={s} className="capitalize">{s}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={needsReview}
              onChange={(e) => setParam("needs_review", e.target.checked ? "1" : "")}
              className="accent-amber-400"
            />
            Needs review only
          </label>
          {hasFilters && (
            <button
              onClick={() => setSearchParams(search ? { q: search } : {})}
              className="text-xs text-gray-500 hover:text-gray-300 px-2 ml-auto"
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {Array.from({ length: 24 }).map((_, i) => (
            <div key={i} className="aspect-square bg-gray-900 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : models.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-gray-600">
          <p className="text-lg">No models found</p>
          <p className="text-sm mt-1">Try scanning your library or adjusting filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {models.map((m) => <ModelCard key={m.id} model={m} />)}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-8">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 rounded bg-gray-900 border border-gray-700 text-sm disabled:opacity-40 hover:border-gray-500 transition-colors"
          >
            Prev
          </button>
          <span className="text-sm text-gray-500">{page} / {totalPages}</span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 rounded bg-gray-900 border border-gray-700 text-sm disabled:opacity-40 hover:border-gray-500 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
