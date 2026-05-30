import { Link, useLocation } from "react-router-dom";
import { Box, FolderOpen, Users, LayoutGrid, EyeOff, Eye } from "lucide-react";
import { useNSFW } from "../context/NSFWContext";

const links = [
  { to: "/",            label: "Library",     icon: LayoutGrid },
  { to: "/creators",    label: "Creators",    icon: Users },
  { to: "/collections", label: "Collections", icon: FolderOpen },
];

export default function Navbar() {
  const { pathname } = useLocation();
  const { showNSFW, toggle } = useNSFW();

  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-8">
      <Link to="/" className="flex items-center gap-2 text-indigo-400 font-bold text-lg shrink-0">
        <Box size={22} />
        STL Inventory
      </Link>

      <div className="flex items-center gap-1 ml-4">
        {links.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors ${
              pathname === to
                ? "bg-indigo-600 text-white"
                : "text-gray-400 hover:text-gray-100 hover:bg-gray-800"
            }`}
          >
            <Icon size={15} />
            {label}
          </Link>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={toggle}
          title={showNSFW ? "Hide NSFW content" : "Show NSFW content"}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors border ${
            showNSFW
              ? "bg-red-950/60 border-red-800 text-red-400 hover:bg-red-900/60"
              : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600"
          }`}
        >
          {showNSFW ? <Eye size={14} /> : <EyeOff size={14} />}
          {showNSFW ? "NSFW On" : "NSFW Off"}
        </button>
      </div>
    </nav>
  );
}
