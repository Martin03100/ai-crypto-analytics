/** Beginner view: one sentence and a traffic light instead of the full analysis. Stored on the account. */

import { useCallback } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";

export function useSimpleMode() {
  const { user, patchUser } = useAuth();
  const setSimple = useCallback(async (value) => {
    patchUser({ simpleMode: value });
    try {
      await api.setUiMode(value);
    } catch {
      /* the choice still applies for this session */
    }
  }, [patchUser]);
  return { simple: user?.simpleMode === true, chosen: user?.simpleMode === true || user?.simpleMode === false, setSimple };
}
