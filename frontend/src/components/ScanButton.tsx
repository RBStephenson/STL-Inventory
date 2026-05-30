import { useState, useEffect } from "react";
import { RefreshCw } from "lucide-react";
import { api, ScanStatus } from "../api/client";

export default function ScanButton() {
  const [status, setStatus] = useState<ScanStatus | null>(null);

  useEffect(() => {
    api.scan.status().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (!status?.running) return;
    const interval = setInterval(() => {
      api.scan.status().then(setStatus).catch(() => {});
    }, 2000);
    return () => clearInterval(interval);
  }, [status?.running]);

  const start = async () => {
    try {
      const s = await api.scan.start();
      setStatus(s);
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {status?.running && (
        <span className="text-xs text-gray-400 animate-pulse">
          Scanning… {status.models_found ?? 0} models, {status.files_found ?? 0} files
        </span>
      )}
      <button
        onClick={start}
        disabled={status?.running}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-sm transition-colors"
      >
        <RefreshCw size={14} className={status?.running ? "animate-spin" : ""} />
        {status?.running ? "Scanning" : "Scan Library"}
      </button>
    </div>
  );
}
