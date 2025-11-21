// js/main.js — floor overview that follows real machine state
(function () {
  const floorBtn = document.querySelector(".floor-btn");

  // Adjust to your backend + machine id
  const API_BASE   = "https://rls-uvzg.onrender.com";
  const MACHINE_ID = "washer-1";
  const POLL_MS    = 5000;

  function applyStatus(state) {
    if (!floorBtn) return;

    floorBtn.classList.remove("ok", "busy", "warn", "done");

    let cls = "ok";
    if (state === "Running") cls = "busy";
    else if (state === "Aborted") cls = "warn";
    else if (state === "Complete") cls = "done";

    floorBtn.classList.add(cls);
    floorBtn.textContent = `Floor 0 — Washer (1) — ${state}`;
  }

  async function pollStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/machines/${MACHINE_ID}`, {
        cache: "no-store"
      });
      if (!res.ok) {
        console.error("Floor status fetch failed:", res.status);
        return;
      }
      const data = await res.json();
      const state = data.state || "Idle";
      applyStatus(state);
    } catch (err) {
      console.error("Error polling floor status:", err);
    }
  }

  // Initial state + polling
  applyStatus("Idle");
  pollStatus();
  setInterval(pollStatus, POLL_MS);
})();
