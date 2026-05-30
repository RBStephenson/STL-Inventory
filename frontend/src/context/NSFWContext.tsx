import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface NSFWContextValue {
  showNSFW: boolean;
  toggle: () => void;
}

const NSFWContext = createContext<NSFWContextValue>({
  showNSFW: false,
  toggle: () => {},
});

export function NSFWProvider({ children }: { children: ReactNode }) {
  const [showNSFW, setShowNSFW] = useState(() => {
    try {
      return localStorage.getItem("showNSFW") === "true";
    } catch {
      return false;
    }
  });

  const toggle = () => {
    setShowNSFW((prev) => {
      const next = !prev;
      localStorage.setItem("showNSFW", String(next));
      return next;
    });
  };

  return (
    <NSFWContext.Provider value={{ showNSFW, toggle }}>
      {children}
    </NSFWContext.Provider>
  );
}

export const useNSFW = () => useContext(NSFWContext);
