export interface CurrencyOption {
  code: string;
  label: string;
}

export interface TimezoneOption {
  value: string;
  label: string;
  offsetMinutes: number;
}

const FALLBACK_CURRENCIES = [
  "AED",
  "AUD",
  "BDT",
  "BRL",
  "CAD",
  "CHF",
  "CNY",
  "CZK",
  "DKK",
  "EGP",
  "EUR",
  "GBP",
  "HKD",
  "HUF",
  "IDR",
  "ILS",
  "INR",
  "JPY",
  "KRW",
  "LKR",
  "MXN",
  "MYR",
  "NOK",
  "NPR",
  "NZD",
  "PHP",
  "PKR",
  "PLN",
  "RON",
  "RUB",
  "SAR",
  "SEK",
  "SGD",
  "THB",
  "TRY",
  "TWD",
  "UAH",
  "USD",
  "VND",
  "ZAR"
];

const FALLBACK_TIMEZONES = [
  "UTC",
  "America/Anchorage",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/New_York",
  "America/Sao_Paulo",
  "Asia/Dhaka",
  "Asia/Dubai",
  "Asia/Hong_Kong",
  "Asia/Jakarta",
  "Asia/Karachi",
  "Asia/Kathmandu",
  "Asia/Kolkata",
  "Asia/Manila",
  "Asia/Seoul",
  "Asia/Shanghai",
  "Asia/Singapore",
  "Asia/Taipei",
  "Asia/Tokyo",
  "Australia/Adelaide",
  "Australia/Brisbane",
  "Australia/Melbourne",
  "Australia/Perth",
  "Australia/Sydney",
  "Europe/Amsterdam",
  "Europe/Berlin",
  "Europe/London",
  "Europe/Madrid",
  "Europe/Paris",
  "Europe/Rome",
  "Pacific/Auckland"
];

const CURRENCY_BY_REGION: Record<string, string> = {
  AE: "AED",
  AU: "AUD",
  BD: "BDT",
  BR: "BRL",
  CA: "CAD",
  CH: "CHF",
  CN: "CNY",
  CZ: "CZK",
  DE: "EUR",
  DK: "DKK",
  EG: "EGP",
  ES: "EUR",
  FR: "EUR",
  GB: "GBP",
  HK: "HKD",
  HU: "HUF",
  ID: "IDR",
  IE: "EUR",
  IL: "ILS",
  IN: "INR",
  IT: "EUR",
  JP: "JPY",
  KR: "KRW",
  LK: "LKR",
  MX: "MXN",
  MY: "MYR",
  NL: "EUR",
  NO: "NOK",
  NP: "NPR",
  NZ: "NZD",
  PH: "PHP",
  PK: "PKR",
  PL: "PLN",
  RO: "RON",
  RU: "RUB",
  SA: "SAR",
  SE: "SEK",
  SG: "SGD",
  TH: "THB",
  TR: "TRY",
  TW: "TWD",
  UA: "UAH",
  US: "USD",
  VN: "VND",
  ZA: "ZAR"
};

type IntlWithSupportedValues = typeof Intl & {
  supportedValuesOf?: (key: "currency" | "timeZone") => string[];
};

function supportedValues(key: "currency" | "timeZone"): string[] {
  const extendedIntl = Intl as IntlWithSupportedValues;
  return extendedIntl.supportedValuesOf?.(key) ?? [];
}

function currencyName(code: string): string {
  if (typeof Intl.DisplayNames !== "function") {
    return code;
  }

  const displayNames = new Intl.DisplayNames(
    [navigator.language || "en"],
    { type: "currency" }
  );

  return displayNames.of(code) ?? code;
}

function currencySymbol(code: string): string {
  try {
    const part = new Intl.NumberFormat(
      navigator.language || "en",
      {
        style: "currency",
        currency: code,
        currencyDisplay: "narrowSymbol",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
      }
    )
      .formatToParts(0)
      .find((item) => item.type === "currency");

    return part?.value ?? code;
  } catch {
    return code;
  }
}

export function getCurrencyOptions(): CurrencyOption[] {
  const codes = supportedValues("currency");
  const values = codes.length > 0 ? codes : FALLBACK_CURRENCIES;

  return [...new Set(values)]
    .map((code) => {
      const name = currencyName(code);
      const symbol = currencySymbol(code);

      return {
        code,
        label:
          symbol === code
            ? `${code} — ${name}`
            : `${code} — ${name} (${symbol})`
      };
    })
    .sort((left, right) => left.label.localeCompare(right.label));
}

function timezoneOffsetMinutes(
  timeZone: string,
  instant: Date = new Date()
): number {
  if (timeZone === "UTC") {
    return 0;
  }

  const date = new Date(instant);
  date.setMilliseconds(0);

  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23"
  });

  const parts = Object.fromEntries(
    formatter
      .formatToParts(date)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value])
  );

  const representedAsUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second)
  );

  return Math.round((representedAsUtc - date.getTime()) / 60000);
}

function formatGmtOffset(offsetMinutes: number): string {
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const hours = Math.floor(absolute / 60)
    .toString()
    .padStart(2, "0");
  const minutes = (absolute % 60)
    .toString()
    .padStart(2, "0");

  return `GMT${sign}${hours}:${minutes}`;
}

export function getTimezoneOptions(): TimezoneOption[] {
  const detected = detectTimezone();
  const supported = supportedValues("timeZone");
  const source = supported.length > 0 ? supported : FALLBACK_TIMEZONES;
  const zones = [...new Set([...source, detected, "UTC"])];

  return zones
    .map((value) => {
      let offsetMinutes = 0;

      try {
        offsetMinutes = timezoneOffsetMinutes(value);
      } catch {
        offsetMinutes = 0;
      }

      return {
        value,
        offsetMinutes,
        label: `(${formatGmtOffset(offsetMinutes)}) ${value}`
      };
    })
    .sort(
      (left, right) =>
        left.offsetMinutes - right.offsetMinutes ||
        left.value.localeCompare(right.value)
    );
}

export function detectDefaultCurrency(): string {
  const locale = navigator.language || "";
  let region = locale.split("-")[1]?.toUpperCase();

  try {
    region = new Intl.Locale(locale).region ?? region;
  } catch {
    // Keep the region parsed from navigator.language.
  }

  return region ? (CURRENCY_BY_REGION[region] ?? "") : "";
}

export function detectTimezone(): string {
  const detected =
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

  if (detected === "Asia/Calcutta") {
    return "Asia/Kolkata";
  }

  return detected;
}
