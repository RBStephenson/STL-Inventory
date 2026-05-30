import { useState, useEffect } from "react";
import { FolderOpen, Plus } from "lucide-react";
import { api, Collection } from "../api/client";

export default function Collections() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  useEffect(() => { api.collections.list().then(setCollections).catch(() => {}); }, []);

  const create = async () => {
    if (!name.trim()) return;
    const col = await api.collections.create(name.trim());
    setCollections((prev) => [...prev, { ...col, model_count: 0 }]);
    setName("");
    setCreating(false);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <FolderOpen size={20} className="text-indigo-400" />
          <h1 className="text-2xl font-bold text-gray-100">Collections</h1>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-sm transition-colors"
        >
          <Plus size={14} />
          New Collection
        </button>
      </div>

      {creating && (
        <div className="flex gap-2 mb-4 p-3 bg-gray-900 rounded border border-gray-800">
          <input
            autoFocus
            type="text"
            placeholder="Collection name…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && create()}
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500"
          />
          <button onClick={create} className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-sm">
            Create
          </button>
          <button onClick={() => setCreating(false)} className="px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-sm text-gray-400">
            Cancel
          </button>
        </div>
      )}

      {collections.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-gray-600">
          <FolderOpen size={48} />
          <p className="mt-3">No collections yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {collections.map((col) => (
            <div
              key={col.id}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-1"
            >
              <p className="font-medium text-gray-100">{col.name}</p>
              {col.description && <p className="text-xs text-gray-500">{col.description}</p>}
              <p className="text-xs text-gray-600 mt-1">{col.model_count} models</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
