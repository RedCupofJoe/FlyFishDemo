import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import countries from "./data/countries.json";
import { ReportView } from "./report-view";
import { markdownBlocks } from "./markdown";
import {
  countryFromTarget,
  seasonFromDate,
  toggleCountry,
  tripPayload,
  validateTrip,
} from "./trip";

describe("route selection", () => {
  it("keeps countries in click order and removes a second click", () => {
    const france = { code: "FR", name: "France" };
    const japan = { code: "JP", name: "Japan" };
    const once = toggleCountry(toggleCountry([], france), japan);
    expect(once.map((country) => country.code)).toEqual(["FR", "JP"]);
    expect(toggleCountry(once, france).map((country) => country.code)).toEqual(["JP"]);
  });

  it("reads the ISO code from a map shape", () => {
    const group = document.createElement("g");
    group.setAttribute("data-iso", "FR");
    const path = document.createElement("path");
    group.appendChild(path);
    expect(countryFromTarget(path)).toBe("FR");
    expect(countryFromTarget(null)).toBeNull();
  });

  it("lists unique countries including small states", () => {
    const codes = countries.map((country) => country.code);
    expect(new Set(codes).size).toBe(codes.length);
    for (const code of ["FR", "SG", "US", "JP", "MV"]) {
      expect(codes).toContain(code);
    }
  });
});

describe("trip form", () => {
  const base = {
    countries: [{ code: "FR", name: "France" }],
    startDate: "2026-06-01",
    endDate: "2026-06-08",
    season: "summer",
    originCode: "US",
    citizenshipStatus: "citizen",
    prompt: "Trains and museums",
  };

  it("derives a northern-hemisphere time of year from the start date", () => {
    expect(seasonFromDate("2026-01-10")).toBe("winter");
    expect(seasonFromDate("2026-07-04")).toBe("summer");
  });

  it("rejects an empty route and a reversed date range", () => {
    expect(validateTrip({ ...base, countries: [] }).join(" ")).toMatch(/at least one country/);
    expect(validateTrip({ ...base, endDate: "2026-05-01" }).join(" ")).toMatch(/end date/);
    expect(validateTrip(base)).toEqual([]);
  });

  it("builds the response-agent payload in route order", () => {
    const payload = tripPayload(
      {
        ...base,
        countries: [
          { code: "FR", name: "France" },
          { code: "JP", name: "Japan" },
        ],
      },
      countries,
      "trip-9",
    );
    expect(payload.countries.map((country) => country.code)).toEqual(["FR", "JP"]);
    expect(payload.origin.name).toMatch(/United States/);
    expect(payload.citizenship_status).toBe("citizen");
  });
});

describe("report rendering", () => {
  it("keeps headings and source lines", () => {
    const blocks = markdownBlocks("# Guide\n\n## France\n\n### Weather\n\n- https://example.com");
    expect(blocks.map((block) => block.kind)).toEqual(["h1", "h2", "h3", "li"]);
  });

  it("renders an assistant report", () => {
    render(<ReportView text={"## France\n\nMild."} />);
    expect(screen.getByText("France")).toBeTruthy();
    expect(screen.getByText("Mild.")).toBeTruthy();
  });
});
