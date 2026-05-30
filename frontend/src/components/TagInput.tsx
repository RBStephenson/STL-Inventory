import { useState, useEffect, useRef, KeyboardEvent } from "react";
import { X } from "lucide-react";

interface TagSuggestion {
  tag: string;
  count: number;
}

interface Props {
  value: string[];
  onChange: (tags: string[]) => void;
  suggestions: TagSuggestion[];
  placeholder?: string;
}

export default function TagInput({ value, onChange, suggestions, placeholder = "Add tag…" }: Props) {
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const filtered = input.trim()
    ? suggestions.filter(
        (s) =>
          s.tag.includes(input.toLowerCase().trim()) &&
          !value.includes(s.tag)
      )
    : [];

  useEffect(() => { setHighlighted(0); }, [input]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        !inputRef.current?.contains(e.target as Node) &&
        !dropdownRef.current?.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const addTag = (tag: string) => {
    const normalised = tag.trim().toLowerCase();
    if (normalised && !value.includes(normalised)) {
      onChange([...value, normalised]);
    }
    setInput("");
    setOpen(false);
    inputRef.current?.focus();
  };

  const removeTag = (tag: string) => {
    onChange(value.filter((t) => t !== tag));
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      if (filtered.length > 0 && open) {
        addTag(filtered[highlighted]?.tag ?? input);
      } else if (input.trim()) {
        addTag(input);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Backspace" && !input && value.length > 0) {
      removeTag(value[value.length - 1]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative">
      <div
        className="flex flex-wrap gap-1.5 p-2 bg-gray-800 border border-gray-700 rounded-lg focus-within:border-indigo-500 cursor-text min-h-[42px]"
        onClick={() => inputRef.current?.focus()}
      >
        {value.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1 bg-indigo-900/60 text-indigo-300 text-xs px-2 py-0.5 rounded-full"
          >
            {tag}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
              className="hover:text-white"
            >
              <X size={10} />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => { setInput(e.target.value); setOpen(true); }}
          onKeyDown={onKeyDown}
          onFocus={() => input && setOpen(true)}
          placeholder={value.length === 0 ? placeholder : ""}
          className="flex-1 min-w-[120px] bg-transparent text-sm text-gray-100 placeholder-gray-600 focus:outline-none"
        />
      </div>

      {/* Dropdown */}
      {open && filtered.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-20 top-full mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden"
        >
          {filtered.slice(0, 10).map((s, i) => (
            <button
              key={s.tag}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); addTag(s.tag); }}
              className={`w-full flex items-center justify-between px-3 py-2 text-sm text-left transition-colors ${
                i === highlighted
                  ? "bg-indigo-600 text-white"
                  : "text-gray-300 hover:bg-gray-700"
              }`}
            >
              <span>{s.tag}</span>
              <span className={`text-xs ${i === highlighted ? "text-indigo-200" : "text-gray-600"}`}>
                {s.count}×
              </span>
            </button>
          ))}
          {/* Create new option if exact match not in suggestions */}
          {input.trim() && !filtered.find((s) => s.tag === input.trim().toLowerCase()) && (
            <button
              type="button"
              onMouseDown={(e) => { e.preventDefault(); addTag(input); }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:bg-gray-700 border-t border-gray-700"
            >
              <span className="text-indigo-400">+</span>
              Create "{input.trim().toLowerCase()}"
            </button>
          )}
        </div>
      )}
      <p className="text-xs text-gray-700 mt-1">Enter or comma to add · Backspace to remove</p>
    </div>
  );
}
