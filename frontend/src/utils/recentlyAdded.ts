/** True when a model's created_at falls within the "recently added" window (#170).
 *  Backend timestamps are naive UTC (no timezone marker), so one is appended
 *  before parsing to avoid the browser reading them as local time. */
export function isRecentlyAdded(
  createdAt: string | null | undefined,
  days: number,
  now: Date = new Date()
): boolean {
  if (!createdAt || days <= 0) return false;
  const iso = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(createdAt) ? createdAt : createdAt + "Z";
  const created = new Date(iso);
  if (isNaN(created.getTime())) return false;
  return now.getTime() - created.getTime() <= days * 86_400_000;
}
