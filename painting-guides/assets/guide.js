/* guide.js — Shared tab switching for 1:6 Scale Painting Guides */
function showTab(id, btn) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
  if (btn) {
    btn.classList.add('active');
  } else {
    // fallback: find button by matching onclick content (no explicit btn passed)
    document.querySelectorAll('.tab-btn').forEach(b => {
      const oc = b.getAttribute('onclick') || '';
      if (oc.includes("'" + id + "'") || oc.includes('"' + id + '"')) b.classList.add('active');
    });
  }
}
