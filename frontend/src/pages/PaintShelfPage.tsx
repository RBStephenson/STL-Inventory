import { Palette } from "lucide-react";

export default function PaintShelfPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="flex items-center gap-2 text-2xl font-bold text-white mb-1">
        <Palette size={22} className="text-indigo-400" />
        Paint Shelf
      </h1>
      <p className="text-sm text-gray-500 mb-8">
        Your paint inventory — the paints guides can draw from.
      </p>
      <div className="bg-gray-900 border border-gray-800 rounded-lg px-6 py-12 text-center">
        <p className="text-sm text-gray-400 mb-1">Coming soon</p>
        <p className="text-xs text-gray-600">
          Track the paints you own here; guides will only ever reference paints from your shelf.
        </p>
      </div>
    </div>
  );
}
