// ── Server clock ──────────────────────────────────────────
const clockEl = document.getElementById("server-time");
function updateClock() {
  if (clockEl) {
    clockEl.textContent = new Date().toLocaleString('en-US', {
      timeZone: 'Asia/Manila',
      hour12: false,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    }).replace(',', '') + ' (GMT+8)';
  }
}
updateClock();
setInterval(updateClock, 1000);

// ── Expand/collapse incident detail rows ──────────────────
function toggleDetail(btn, incidentId) {
  const row = document.getElementById("detail-" + incidentId);
  if (!row) return;
  const isHidden = row.style.display === "none" || row.style.display === "";
  row.style.display = isHidden ? "table-row" : "none";
  if (isHidden) {
    btn.innerHTML = "▲ collapse";
  } else {
    btn.innerHTML = "▼ expand";
  }
}

// ── On-call toggle via fetch ───────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".oncall-toggle").forEach((checkbox) => {
    checkbox.addEventListener("change", async function () {
      const engineerId = this.dataset.id;
      try {
        const resp = await fetch(`/engineers/${engineerId}/toggle-oncall`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        if (!resp.ok) {
          this.checked = !this.checked; // revert
          alert("Failed to update on-call status.");
        }
      } catch (e) {
        this.checked = !this.checked;
        alert("Network error. Could not update on-call status.");
      }
    });
  });
});
