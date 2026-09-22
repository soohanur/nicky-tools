"use client";

import { useEffect, useState } from "react";

// Load `fetcher()` on mount (and every `every` ms when set). `reload()` refetches.
export function useFetch(fetcher, { every = 0 } = {}) {
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const data = await fetcher();
        if (alive) setState({ data, error: "", loading: false });
      } catch (e) {
        if (alive) setState((s) => ({ ...s, error: e.message, loading: false }));
      }
    };
    run();
    const timer = every ? setInterval(run, every) : null;
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
    };
  }, [fetcher, every, tick]);

  return { ...state, reload: () => setTick((t) => t + 1), setData: (data) => setState((s) => ({ ...s, data })) };
}
