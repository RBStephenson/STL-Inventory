// Library tag chips cycle: off → include → exclude → off (#205).
// Returns the next URL param values for the `tag` / `exclude_tag` pair when
// `clicked` is clicked. The two params are mutually exclusive by construction.
export function nextTagParams(
  clicked: string,
  activeTag: string,
  excludeTag: string,
): { tag: string; exclude_tag: string } {
  if (activeTag === clicked) return { tag: "", exclude_tag: clicked }; // include → exclude
  if (excludeTag === clicked) return { tag: "", exclude_tag: "" };     // exclude → off
  return { tag: clicked, exclude_tag: "" };                            // off (or other tag active) → include
}
