/** API client: error handling and response normalization. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { humanizeError } from "../i18n/errorMessages";

function jsonResponse(body, { status = 200, headers = {} } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (k) => headers[k] ?? null },
    json: async () => {
      if (typeof body === "string") throw new SyntaxError("Unexpected token <");
      return body;
    },
  };
}

beforeEach(() => {
  vi.stubGlobal("document", { cookie: "aca_csrf=tok" });
  vi.stubGlobal("localStorage", { getItem: () => "en", setItem: () => {}, removeItem: () => {} });
  vi.stubGlobal("window", { dispatchEvent: vi.fn() });
  vi.stubGlobal("Event", class { constructor(type) { this.type = type; } });
});
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

async function loadApi(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  vi.resetModules();
  return (await import("../api")).api;
}

describe("request errors", () => {
  it("turns a failed fetch into a friendly network error", async () => {
    const api = await loadApi(async () => { throw new TypeError("Failed to fetch"); });
    const err = await api.headlines().catch((e) => e);
    expect(err.code).toBe("network");
    expect(humanizeError(err, "en")).toMatch(/connect/i);
  });

  it("aborts requests that take too long", async () => {
    vi.useFakeTimers();
    const api = await loadApi((_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
    }));
    const pending = api.headlines().catch((e) => e);
    await vi.advanceTimersByTimeAsync(61_000);
    const err = await pending;
    expect(err.code).toBe("timeout");
    expect(humanizeError(err, "en")).toMatch(/timed out/i);
  });

  it("reports a non-JSON success body instead of crashing", async () => {
    const api = await loadApi(async () => jsonResponse("<html>proxy</html>"));
    const err = await api.events().catch((e) => e);
    expect(err.status).toBe(502);
    expect(humanizeError(err, "en")).not.toBe("");
  });

  it("keeps a status-based message for non-JSON error pages", async () => {
    const api = await loadApi(async () => jsonResponse("<html>Bad gateway</html>", { status: 502 }));
    const err = await api.events().catch((e) => e);
    expect(err.message).toBe("Server error (502)");
  });
});

describe("response normalization", () => {
  it("always gives list endpoints an array", async () => {
    const api = await loadApi(async () => jsonResponse({}));
    expect((await api.headlines()).headlines).toEqual([]);
    expect((await api.events()).events).toEqual([]);
    expect((await api.searchCoins("x")).results).toEqual([]);
    expect((await api.onchain()).items).toEqual([]);
    expect(await api.listApiKeys()).toEqual([]);
    const history = await api.portfolioHistory();
    expect(history.items).toEqual([]);
    expect(history.total).toBe(0);
  });

  it("drops malformed history entries and fills nested defaults", async () => {
    const api = await loadApi(async () => jsonResponse({ items: [{}, null, { id: 3 }], total: 3 }));
    const res = await api.portfolioHistory();
    expect(res.items).toEqual([{ id: 3, holdings: [], analysis_data: {} }]);
  });

  it("marks an AI result without data as unsuccessful", async () => {
    const api = await loadApi(async () => jsonResponse({ success: true, data: null }));
    const res = await api.generateForecast("quant", "BTC", "1T");
    expect(res.success).toBe(false);
    expect(res.data).toBeNull();
  });

  it("filters invalid chart points and clamps Fear & Greed", async () => {
    let call = 0;
    const api = await loadApi(async () => {
      call += 1;
      return call === 1
        ? jsonResponse({ prices: [[1, 10], [2, null], "x", [3, "11"]] })
        : jsonResponse({ data: { value: 140, classification: "Extreme Greed" } });
    });
    expect((await api.marketChart("bitcoin")).prices).toEqual([[1, 10], [3, 11]]);
    expect((await api.fearGreed()).data.value).toBe(100);
  });

  it("returns null Fear & Greed data when the value is missing", async () => {
    const api = await loadApi(async () => jsonResponse({ data: {} }));
    expect((await api.fearGreed()).data).toBeNull();
  });
});

describe("humanizeError", () => {
  it("maps a market-history failure to the free-model message", () => {
    const msg = humanizeError("Chyba pri nacitani historickych dat: HTTPSConnectionPool 403 Forbidden", "en");
    expect(msg).toMatch(/free model/i);
  });
});

describe("AI failure messages", () => {
  it.each([
    ["AI vratila 23 bodov namiesto 24.", /invalid response/i],
    ["Chyba pri parsovani JSON: Expecting value", /invalid response/i],
    ["Gemini API chyba: 400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key.", /API key/i],
    ["Gemini API chyba: 400 INVALID_ARGUMENT. Thinking level is not supported", /rejected the request/i],
    ["Gemini API chyba: [Errno -3] Temporary failure in name resolution", /connect/i],
  ])("maps %s", (raw, expected) => {
    expect(humanizeError(raw, "en")).toMatch(expected);
  });

  it("uses the demo-data fallback instead of the generic message", () => {
    expect(humanizeError("some brand new provider error", "en", "errors.aiFallback")).toMatch(/demo data/i);
    expect(humanizeError("some brand new provider error", "en")).toMatch(/something went wrong/i);
  });
});

describe("background AI jobs", () => {
  it("starts the forecast as a job and polls until it is done", async () => {
    vi.useFakeTimers();
    const calls = [];
    let polls = 0;
    const api = await loadApi(async (url, init) => {
      calls.push([url, init?.method || "GET", init?.headers?.Prefer]);
      if (url === "/api/forecast") return jsonResponse({ job_id: "job-123" }, { status: 202 });
      polls += 1;
      return jsonResponse(polls < 3 ? { status: "running" } : { status: "done", result: { success: true, data: { ceny: [1] } } });
    });
    const pending = api.generateForecast("gemini", "BTC", "1T");
    await vi.advanceTimersByTimeAsync(3_500);
    const res = await pending;
    expect(res.success).toBe(true);
    expect(calls[0]).toEqual(["/api/forecast", "POST", "respond-async"]);
    expect(calls.slice(1).every(([url]) => url === "/api/jobs/job-123")).toBe(true);
  });

  it("still accepts an inline answer from a server without jobs", async () => {
    const api = await loadApi(async () => jsonResponse({ success: true, data: { reply: "hi" } }));
    expect((await api.sendChatMessage("gemini", [])).data.reply).toBe("hi");
  });
});

describe("job polling resilience", () => {
  it("keeps waiting through a proxy 502 while the job finishes", async () => {
    vi.useFakeTimers();
    let polls = 0;
    const api = await loadApi(async (url) => {
      if (url === "/api/forecast") return jsonResponse({ job_id: "job-9" }, { status: 202 });
      polls += 1;
      if (polls === 1) return jsonResponse("<html>Bad gateway</html>", { status: 502 });
      return jsonResponse({ status: "done", result: { success: true, data: { ceny: [2] } } });
    });
    const pending = api.generateForecast("gemini", "BTC", "1T");
    await vi.advanceTimersByTimeAsync(6_000);
    expect((await pending).success).toBe(true);
  });
});

describe("cold start", () => {
  it("retries a read once after a gateway timeout, but never a write", async () => {
    vi.useFakeTimers();
    let n = 0;
    const api = await loadApi(async () => (++n === 1 ? jsonResponse("<html>", { status: 504 }) : jsonResponse({ headlines: [] })));
    const pending = api.headlines();
    await vi.advanceTimersByTimeAsync(2_100);
    expect((await pending).headlines).toEqual([]);
    expect(n).toBe(2);

    let writes = 0;
    const api2 = await loadApi(async () => { writes += 1; return jsonResponse("<html>", { status: 504 }); });
    const err = await api2.vote("Bullish").catch((e) => e);
    expect(err.status).toBe(504);
    expect(writes).toBe(1);
  });
});
