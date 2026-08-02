import { useEffect, useMemo, useState } from "react";
import type { ClauseChange } from "../data/negotiation";
import { friendlyApiError, generateChangeSummary } from "../lib/api";

export function useAiChangeSummary(changes: ClauseChange[] | undefined) {
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState("");
  const signature = useMemo(() => JSON.stringify(changes ?? []), [changes]);

  useEffect(() => {
    if (!changes?.length) {
      setLines([]);
      setError("");
      return;
    }

    let active = true;
    setLines([]);
    setError("");
    void generateChangeSummary(
      changes.map((change) => ({
        title: `${change.clauseNo} ${change.title}`,
        before: change.prevText ?? "",
        after: change.newText ?? "",
      })),
    )
      .then((result) => {
        if (active) setLines(result.lines);
      })
      .catch((reason: unknown) => {
        if (active) setError(friendlyApiError(reason));
      });

    return () => {
      active = false;
    };
  }, [signature]);

  return { lines, error, loading: Boolean(changes?.length) && !lines.length && !error };
}
