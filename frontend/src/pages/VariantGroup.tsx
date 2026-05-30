import { useEffect, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { ArrowLeft, Layers } from "lucide-react";
import { api, Model } from "../api/client";
import ModelCard from "../components/ModelCard";

export default function VariantGroup() {
  const { creatorId, character } = useParams<{ creatorId: string; character: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [variants, setVariants] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);

  const decodedCharacter = character ? decodeURIComponent(character) : "";
  const numCreatorId = Number(creatorId);

  useEffect(() => {
    if (!numCreatorId || !decodedCharacter) return;
    setLoading(true);
    api.models
      .variants(numCreatorId, decodedCharacter)
      .then((data) => setVariants(data.items))
      .finally(() => setLoading(false));
  }, [numCreatorId, decodedCharacter]);

  const creatorName = variants[0]?.character
    ? null
    : null;
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(from)}
          className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </button>
        <div className="h-4 w-px bg-gray-700" />
        <Layers size={16} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-white">{decodedCharacter}</h1>
        {!loading && (
          <span className="text-sm text-gray-400">
            {variants.length} variant{variants.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {loading ? (
        <div className="flex justify-center py-24 text-gray-500 text-sm">Loading…</div>
      ) : variants.length === 0 ? (
        <div className="flex justify-center py-24 text-gray-500 text-sm">No variants found.</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {variants.map((model) => (
            <ModelCard key={model.id} model={model} />
          ))}
        </div>
      )}
    </div>
  );
}
