/** Premium mode (admin switch) and whether the signed-in user has Premium. With the mode off nothing paid is shown.
 *
 * `features`: the user may use the paid features. While Premium mode is off they are free for everyone (and shown
 * without any Premium label); once it is on, only members keep them. */

import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";

export function usePremium() {
  const { premium, loaded } = useAppConfig();
  const { user } = useAuth();
  const mode = Boolean(premium?.enabled);
  const active = mode && Boolean(user?.premium);
  return { mode, active, features: Boolean(user) && (!mode || active), info: mode ? premium : null, loaded };
}
