/** Premium mode (admin switch) and whether the signed-in user has Premium. With the mode off nothing paid is shown. */

import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";

export function usePremium() {
  const { premium, loaded } = useAppConfig();
  const { user } = useAuth();
  const mode = Boolean(premium?.enabled);
  return { mode, active: mode && Boolean(user?.premium), info: mode ? premium : null, loaded };
}
