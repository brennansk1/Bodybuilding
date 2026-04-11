/**
 * Shared form validation helpers used by onboarding / settings /
 * checkin save flows. Keeps validation logic out of individual pages
 * and lets us produce consistent toast messages for missing fields.
 */

export type FieldValue = string | number | boolean | null | undefined | Array<unknown>;

/**
 * Returns a human-readable error message if any required field is empty,
 * or `null` if everything looks good.
 *
 * A field is considered empty when:
 *   - value === null or undefined
 *   - value is a string with zero length after trimming
 *   - value is an array of length 0
 *   - value is numeric and NaN
 */
export function validateRequired(
  fields: Record<string, FieldValue>,
  labels: Record<string, string>
): string | null {
  const missing: string[] = [];
  for (const key of Object.keys(fields)) {
    const value = fields[key];
    if (value === null || value === undefined) {
      missing.push(labels[key] || key);
      continue;
    }
    if (typeof value === "string" && value.trim() === "") {
      missing.push(labels[key] || key);
      continue;
    }
    if (typeof value === "number" && Number.isNaN(value)) {
      missing.push(labels[key] || key);
      continue;
    }
    if (Array.isArray(value) && value.length === 0) {
      missing.push(labels[key] || key);
      continue;
    }
  }
  if (missing.length === 0) return null;
  if (missing.length === 1) return `Missing required field: ${missing[0]}`;
  return `Missing required fields: ${missing.join(", ")}`;
}

/**
 * Standard numeric range check. Returns the first failing message, or null.
 * Example: validateRanges({ age: 25 }, { age: { min: 14, max: 100, label: "Age" } })
 */
export function validateRanges(
  fields: Record<string, number | null | undefined>,
  rules: Record<string, { min?: number; max?: number; label: string }>
): string | null {
  for (const key of Object.keys(rules)) {
    const value = fields[key];
    if (value === null || value === undefined || Number.isNaN(value)) continue;
    const rule = rules[key];
    if (rule.min !== undefined && value < rule.min) {
      return `${rule.label} must be at least ${rule.min}`;
    }
    if (rule.max !== undefined && value > rule.max) {
      return `${rule.label} must be at most ${rule.max}`;
    }
  }
  return null;
}

/**
 * Pull a user-facing message out of an axios/fetch error. Prefers the
 * FastAPI `detail` field, falls back to `message`, then a default.
 */
export function extractErrorMessage(err: unknown, fallback = "Something went wrong"): string {
  if (!err) return fallback;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const anyErr = err as any;
  const detail = anyErr?.response?.data?.detail ?? anyErr?.data?.detail ?? anyErr?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // Pydantic validation errors: list of {loc, msg, type}
    const first = detail[0];
    if (first?.msg) {
      const loc = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null;
      return loc ? `${loc}: ${first.msg}` : first.msg;
    }
  }
  if (typeof anyErr?.message === "string") return anyErr.message;
  return fallback;
}
