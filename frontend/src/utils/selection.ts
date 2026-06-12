/**
 * Compute the next multi-select set after a card is clicked (#164).
 *
 * Plain click toggles a single id. Shift-click, when there's an anchor (the last
 * card clicked without Shift), adds the inclusive range between the anchor and
 * the clicked card, in the given grid order. A shift-click with no valid anchor
 * falls back to a single toggle.
 */
export function nextSelection(
  prev: Set<number>,
  orderedIds: number[],
  anchor: number | null,
  id: number,
  shiftKey: boolean,
): Set<number> {
  const next = new Set(prev);
  if (shiftKey && anchor != null && anchor !== id) {
    const a = orderedIds.indexOf(anchor);
    const b = orderedIds.indexOf(id);
    if (a !== -1 && b !== -1) {
      const [lo, hi] = a < b ? [a, b] : [b, a];
      for (let i = lo; i <= hi; i++) next.add(orderedIds[i]);
      return next;
    }
  }
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}
