"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import Icon from "@/components/ui/Icon";

const ToastContext = createContext(() => {});

// Bottom-centre toast, one at a time, same look as the prototype's toast().
export function ToastProvider({ children }) {
  const [msg, setMsg] = useState("");
  const [show, setShow] = useState(false);
  const timer = useRef(null);

  const toast = useCallback((text) => {
    setMsg(text);
    setShow(false);
    requestAnimationFrame(() => setShow(true));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setShow(false), 2500);
  }, []);

  useEffect(() => () => timer.current && clearTimeout(timer.current), []);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className={`toast${show ? " show" : ""}`} role="status" aria-live="polite">
        <Icon name="check" />
        <span>{msg}</span>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
