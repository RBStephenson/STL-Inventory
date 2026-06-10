import { Paintbrush } from "lucide-react";

export default function GuidesPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="flex items-center gap-2 text-2xl font-bold text-white mb-1">
        <Paintbrush size={22} className="text-indigo-400" />
        Painting Guides
      </h1>
      <p className="text-sm text-gray-500 mb-8">
        Step-by-step painting guides for your models.
      </p>
      <div className="bg-gray-900 border border-gray-800 rounded-lg px-6 py-12 text-center">
        <p className="text-sm text-gray-400 mb-1">Coming soon</p>
        <p className="text-xs text-gray-600">
          Guides you create will appear here, with color recipes, techniques, and printable exports.
        </p>
      </div>
    </div>
  );
}
