import { describe, expect, it } from "vitest";
import { parsePortfolioCsv } from "../utils/portfolioCsv";

describe("parsePortfolioCsv", () => {
  it("reads a simple coin,amount file with a header", () => {
    const r = parsePortfolioCsv("coin,amount\nBTC,0.5\neth,2\n");
    expect(r).toEqual({ holdings: [{ symbol: "BTC", amount: 0.5 }, { symbol: "ETH", amount: 2 }], errors: [] });
  });

  it("works without a header row", () => {
    expect(parsePortfolioCsv("SOL,10\nADA,1500").holdings).toEqual([{ symbol: "SOL", amount: 10 }, { symbol: "ADA", amount: 1500 }]);
  });

  it("prefers Total over Available in an exchange balance export and skips zero balances", () => {
    const csv = "Coin,Total,Available,In Order,BTC Value\nBTC,1.2,1.0,0.2,1.2\nDOGE,0,0,0,0\nUSDT,\"1,250.50\",1000,250.5,0.02\n";
    expect(parsePortfolioCsv(csv).holdings).toEqual([{ symbol: "BTC", amount: 1.2 }, { symbol: "USDT", amount: 1250.5 }]);
  });

  it("handles semicolons with decimal commas and a BOM", () => {
    const csv = "﻿Minca;Množstvo\r\nBTC;0,25\r\nETH;1,5\r\n";
    expect(parsePortfolioCsv(csv).holdings).toEqual([{ symbol: "BTC", amount: 0.25 }, { symbol: "ETH", amount: 1.5 }]);
  });

  it("sums duplicate coins", () => {
    expect(parsePortfolioCsv("asset,quantity\nBTC,0.1\nBTC,0.2").holdings[0].amount).toBeCloseTo(0.3);
  });

  it("reports bad rows with their line numbers instead of failing the whole file", () => {
    const r = parsePortfolioCsv("coin,amount\nBTC,abc\n<script>,1\nETH,-1\nSOL,3");
    expect(r.holdings).toEqual([{ symbol: "SOL", amount: 3 }]);
    expect(r.errors).toEqual([{ line: 2, reason: "amount" }, { line: 3, reason: "symbol" }, { line: 4, reason: "amount" }]);
  });

  it("explains when a header is present but the needed columns are not", () => {
    expect(parsePortfolioCsv("coin,price\nBTC,60000").errors).toEqual([{ line: 1, reason: "noColumns" }]);
  });

  it("returns nothing for an empty file", () => {
    expect(parsePortfolioCsv("\n\n")).toEqual({ holdings: [], errors: [] });
  });
});
