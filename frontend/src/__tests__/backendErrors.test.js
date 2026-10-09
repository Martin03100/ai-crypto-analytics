/** Every error message the backend can show a user has a translation (the app maps the Slovak text to a key). */

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeAll, describe, expect, it } from "vitest";
import { humanizeError } from "../i18n/errorMessages";
import { loadLanguage } from "../i18n/translations";

const BACKEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../backend/app");
// Not shown to users of the app: machine-to-machine answers and the admin's own tools.
const IGNORED = [/^Not found$/, /^Invalid (signature|payload)\.$/, /ADMIN_USERNAMES/, /^Stripe /i];

function pythonFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return name === "__pycache__" ? [] : pythonFiles(full);
    return name.endsWith(".py") ? [full] : [];
  });
}

function backendDetails() {
  const found = new Set();
  for (const file of pythonFiles(BACKEND)) {
    const source = readFileSync(file, "utf-8");
    for (const m of source.matchAll(/detail=f?"((?:[^"\\]|\\.)+)"/g)) {
      found.add(m[1].replace(/\{[^}]*\}/g, "5"));     // f-string fields become a sample number
    }
  }
  return [...found].filter((d) => !IGNORED.some((re) => re.test(d)));
}

beforeAll(async () => { await loadLanguage("de"); });

describe("backend error messages", () => {
  it("are found in the backend source", () => {
    expect(backendDetails().length).toBeGreaterThan(40);
  });

  it("all have a translation", () => {
    const generic = humanizeError("zzz unknown zzz", "de");
    const missing = backendDetails().filter((d) => {
      const out = humanizeError(d, "de");
      return out === d || out === generic;
    });
    expect(missing).toEqual([]);
  });
});
