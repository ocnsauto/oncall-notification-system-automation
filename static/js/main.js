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
  btn.innerHTML = isHidden ? "▲ collapse" : "▼ expand";
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
          this.checked = !this.checked;
          alert("Failed to update on-call status.");
        }
      } catch (e) {
        this.checked = !this.checked;
        alert("Network error. Could not update on-call status.");
      }
    });
  });
});

// ── Dashboard: smart live update (preserves expanded rows) ─
(function dashboardLiveUpdate() {
  const tbody = document.querySelector("#incidents-table tbody");
  if (!tbody) return;

  async function fetchAndPatch() {
    // Track which rows are currently expanded
    const expanded = new Set();
    document.querySelectorAll(".detail-row").forEach(row => {
      if (row.style.display === "table-row") {
        const id = row.id.replace("detail-", "");
        expanded.add(id);
      }
    });

    try {
      const resp = await fetch(window.location.href, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!resp.ok) return;
      const html = await resp.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const newTbody = doc.querySelector("#incidents-table tbody");
      if (!newTbody) return;

      tbody.innerHTML = newTbody.innerHTML;

      // Re-expand rows that were open before refresh
      expanded.forEach(id => {
        const row = document.getElementById("detail-" + id);
        const btn = document.querySelector(`[onclick*="toggleDetail"][onclick*="${id}"]`);
        if (row) {
          row.style.display = "table-row";
          if (btn) btn.innerHTML = "▲ collapse";
        }
      });

      // Also refresh stat cards (active count etc.)
      const newStatValues = doc.querySelectorAll(".stat-value");
      const statValues = document.querySelectorAll(".stat-value");
      newStatValues.forEach((el, i) => {
        if (statValues[i]) statValues[i].textContent = el.textContent;
      });
    } catch (e) {
      // silently ignore network errors during background poll
    }
  }

  // Engineers sync fires at t=0s, dashboard fetch fires at t=3s.
  // Both cycle every 15s — dashboard always reads the post-sync DB state.
  setTimeout(() => {
    fetchAndPatch();
    setInterval(fetchAndPatch, 15000);
  }, 3000);
})();

// ── Engineers page: auto-sync poller ──────────────────────
(function engineersAutoSync() {
  // Only run on the engineers list page
  if (!document.getElementById("engineers-table")) return;

  const AUTO_SYNC_KEY = "oncall_auto_sync_enabled";

  function isSyncEnabled() {
    return localStorage.getItem(AUTO_SYNC_KEY) !== "false";
  }

  async function doSync() {
    if (!isSyncEnabled()) return;
    try {
      const resp = await fetch("/schedules/api/sync", { method: "POST" });
      if (!resp.ok) return;
      // After syncing, reload just the table by fetching the page HTML
      const pageResp = await fetch(window.location.href);
      if (!pageResp.ok) return;
      const html = await pageResp.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const newTbody = doc.querySelector("#engineers-table tbody");
      const tbody = document.querySelector("#engineers-table tbody");
      if (newTbody && tbody) {
        tbody.innerHTML = newTbody.innerHTML;
        // Re-attach oncall-toggle listeners
        tbody.querySelectorAll(".oncall-toggle").forEach((checkbox) => {
          checkbox.addEventListener("change", async function () {
            const engineerId = this.dataset.id;
            try {
              const r = await fetch(`/engineers/${engineerId}/toggle-oncall`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
              });
              if (!r.ok) { this.checked = !this.checked; alert("Failed to update."); }
            } catch (e) { this.checked = !this.checked; }
          });
        });
      }
    } catch (e) {
      // silently ignore
    }
  }

  setInterval(doSync, 15000);
})();

// ── Schedules: auto-sync toggle button ────────────────────
(function schedulesAutoSyncToggle() {
  const btn = document.getElementById("auto-sync-toggle-btn");
  if (!btn) return;

  const AUTO_SYNC_KEY = "oncall_auto_sync_enabled";

  function updateBtnLabel() {
    const enabled = localStorage.getItem(AUTO_SYNC_KEY) !== "false";
    btn.textContent = enabled ? "⏸ Auto-Sync: ON" : "▶ Auto-Sync: OFF";
    btn.classList.toggle("btn--ok", enabled);
    btn.classList.toggle("btn--ghost", !enabled);
  }

  updateBtnLabel();

  btn.addEventListener("click", () => {
    const current = localStorage.getItem(AUTO_SYNC_KEY) !== "false";
    localStorage.setItem(AUTO_SYNC_KEY, current ? "false" : "true");
    updateBtnLabel();
  });
})();
