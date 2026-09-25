export type Country = {
  code: string;
  name: string;
};

export type TripInput = {
  countries: Country[];
  startDate: string;
  endDate: string;
  season: string;
  originCode: string;
  citizenshipStatus: string;
  prompt: string;
};

export const CITIZENSHIP_OPTIONS = [
  { value: "citizen", label: "Citizen" },
  { value: "permanent_resident", label: "Permanent resident" },
  { value: "visa_holder", label: "Visa holder" },
  { value: "dual_citizen", label: "Dual citizen" },
  { value: "refugee", label: "Refugee or protected status" },
  { value: "other", label: "Other" },
];

export const SEASONS = ["winter", "spring", "summer", "autumn", "wet season", "dry season"];

export function seasonFromDate(isoDate: string): string {
  const month = Number(isoDate.slice(5, 7));
  if (month === 12 || month <= 2) {
    return "winter";
  }
  if (month <= 5) {
    return "spring";
  }
  if (month <= 8) {
    return "summer";
  }
  return "autumn";
}

export function toggleCountry(order: Country[], country: Country): Country[] {
  if (order.some((item) => item.code === country.code)) {
    return order.filter((item) => item.code !== country.code);
  }
  return [...order, country];
}

export function countryFromTarget(target: EventTarget | null): string | null {
  if (!(target instanceof Element)) {
    return null;
  }
  return target.closest("[data-iso]")?.getAttribute("data-iso") ?? null;
}

export function validateTrip(input: TripInput): string[] {
  const errors: string[] = [];
  if (input.countries.length === 0) {
    errors.push("Select at least one country on the map.");
  }
  if (!input.originCode) {
    errors.push("Select your country of origin.");
  }
  if (!input.citizenshipStatus) {
    errors.push("Select your citizenship status.");
  }
  if (!input.season.trim()) {
    errors.push("Select a time of year.");
  }
  if (!input.prompt.trim()) {
    errors.push("Enter a prompt for the report.");
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input.startDate) || !/^\d{4}-\d{2}-\d{2}$/.test(input.endDate)) {
    errors.push("Choose a start date and an end date.");
    return errors;
  }
  if (input.endDate < input.startDate) {
    errors.push("The end date must be on or after the start date.");
  }
  return errors;
}

export function tripPayload(input: TripInput, countries: Country[], tripId: string) {
  const origin = countries.find((country) => country.code === input.originCode);
  return {
    trip_id: tripId,
    countries: input.countries.map((country) => ({ code: country.code, name: country.name })),
    start_date: input.startDate,
    end_date: input.endDate,
    season: input.season,
    origin: { code: input.originCode, name: origin?.name ?? input.originCode },
    citizenship_status: input.citizenshipStatus,
    prompt: input.prompt.trim(),
    user_id: "traveler",
  };
}
