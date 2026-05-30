import { useState, useEffect } from "react";
import { Save, X, Loader2 } from "lucide-react";
import { api, ModelDetail } from "../api/client";
import TagInput from "./TagInput";

interface Props {
  model: ModelDetail;
  onSaved: () => void;
  onCancel: () => void;
}

const SITES = ["myminifactory", "gumroad", "cults3d", "printables", "thingiverse", "thangs", "makerworld", "patreon", "other"];

export default function MetadataEditor({ model, onSaved, onCancel }: Props) {
  const [form, setForm] = useState({
    title:        model.title        ?? "",
    description:  model.description  ?? "",
    notes:        model.notes        ?? "",
    source_url:   model.source_url   ?? "",
    source_site:  model.source_site  ?? "",
    license:      model.license      ?? "",
    category:     model.category     ?? "",
    creator_name: model.creator?.name ?? "",
    tags:         model.tags         ?? [],
    nsfw:         model.nsfw         ?? false,
  });

  const [tagSuggestions, setTagSuggestions] = useState<{ tag: string; count: number }[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.models.tags().then(setTagSuggestions).catch(() => {});
  }, []);

  const set = (key: string, value: unknown) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.models.update(model.id, form);
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );

  const inputClass =
    "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500 transition-colors";

  return (
    <div className="flex flex-col gap-5 bg-gray-900/50 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-200">Edit Metadata</h3>
        <button onClick={onCancel} className="text-gray-600 hover:text-gray-400">
          <X size={16} />
        </button>
      </div>

      <Field label="Title">
        <input
          type="text"
          value={form.title}
          onChange={(e) => set("title", e.target.value)}
          placeholder={model.name}
          className={inputClass}
        />
      </Field>

      <Field label="Creator">
        <input
          type="text"
          value={form.creator_name}
          onChange={(e) => set("creator_name", e.target.value)}
          className={inputClass}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Source Site">
          <select
            value={form.source_site}
            onChange={(e) => set("source_site", e.target.value)}
            className={inputClass}
          >
            <option value="">Unknown</option>
            {SITES.map((s) => (
              <option key={s} value={s} className="capitalize">{s}</option>
            ))}
          </select>
        </Field>
        <Field label="License">
          <input
            type="text"
            value={form.license}
            onChange={(e) => set("license", e.target.value)}
            placeholder="e.g. CC BY-NC"
            className={inputClass}
          />
        </Field>
      </div>

      <Field label="Source URL">
        <input
          type="url"
          value={form.source_url}
          onChange={(e) => set("source_url", e.target.value)}
          placeholder="https://…"
          className={inputClass}
        />
      </Field>

      <Field label="Category">
        <input
          type="text"
          value={form.category}
          onChange={(e) => set("category", e.target.value)}
          placeholder="e.g. Figures, Busts, Terrain…"
          className={inputClass}
        />
      </Field>

      {/* NSFW toggle */}
      <label className="flex items-center gap-3 cursor-pointer select-none">
        <div
          onClick={() => set("nsfw", !form.nsfw)}
          className={`relative w-10 h-6 rounded-full transition-colors ${
            form.nsfw ? "bg-red-600" : "bg-gray-700"
          }`}
        >
          <span
            className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
              form.nsfw ? "translate-x-5" : "translate-x-1"
            }`}
          />
        </div>
        <div>
          <p className="text-sm text-gray-300 font-medium">NSFW</p>
          <p className="text-xs text-gray-600">Blurs thumbnail in the library grid</p>
        </div>
      </label>

      <Field label="Tags">
        <TagInput
          value={form.tags}
          onChange={(tags) => set("tags", tags)}
          suggestions={tagSuggestions}
        />
      </Field>

      <Field label="Description">
        <textarea
          value={form.description}
          onChange={(e) => set("description", e.target.value)}
          rows={4}
          className={`${inputClass} resize-y`}
        />
      </Field>

      <Field label="Notes (private)">
        <textarea
          value={form.notes}
          onChange={(e) => set("notes", e.target.value)}
          rows={2}
          placeholder="Your personal notes about this model…"
          className={`${inputClass} resize-y`}
        />
      </Field>

      {error && (
        <p className="text-sm text-red-400 bg-red-950/40 border border-red-800 rounded px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm text-gray-300 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={save}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-sm transition-colors"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save
        </button>
      </div>
    </div>
  );
}
