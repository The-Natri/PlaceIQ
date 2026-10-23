import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

/**
 * Loads one GET endpoint and tracks its state.
 *   const { data, loading, error, reload } = useApi("/drives");
 * Pass null as the path to skip loading (e.g. until an id is known).
 *
 * reload() keeps the previous data on screen until the new data arrives, so
 * tables don't flash empty. A *different* path clears the old data first,
 * so one record's details never show while another's are loading.
 */
export function useApi(path) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState("");
  const lastPath = useRef(path);

  const load = useCallback(async () => {
    if (lastPath.current !== path) {
      lastPath.current = path;
      setData(null);
    }
    if (!path) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await api.get(path);
      // Ignore a late response for a path we've since moved away from.
      if (lastPath.current === path) setData(result);
    } catch (err) {
      if (lastPath.current === path) setError(err.message);
    } finally {
      if (lastPath.current === path) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load, setData };
}
