// js/main.js
(async function () {
  const floorBtn = document.querySelector(".floor-btn");

  function applyStatus(state) {
    // You can style via CSS: .ok, .busy, .warn, .done
    if (!floorBtn) return;
    floorBtn.classList.remove("ok", "busy", "warn", "done");
    let cls = "ok";
    if (state === "Running") cls = "busy";
    else if (state === "Aborted") cls = "warn";
    else if (state === "Complete") cls = "done";
    floorBtn.classList.add(cls);
    // Optional: append remaining time
    if (state === "Running" && window.__washer?.remaining_s >= 0) {
      const m = Math.floor(window.__washer.remaining_s / 60);
      const s = String(window.__washer.remaining_s % 60).padStart(2, "0");
      floorBtn.textContent = `Floor 0 — Washer (1) — ${m}:${s}`;
    } else {
      floorBtn.textContent = "Floor 0 — Washer (1)";
    }
  }

  function handleState(w) {
    window.__washer = w;
    applyStatus(w.state);
  }

  // Prefer SSE, fallback to polling
  try {
    const es = new EventSource("/api/stream");
    es.addEventListener("init", (e) => handleState(JSON.parse(e.data)));
    es.addEventListener("state", (e) => handleState(JSON.parse(e.data)));
  } catch {
    // Poll every 2s
    setInterval(async () => {
      try {
        const r = await fetch("/api/machines/washer-1/state");
        handleState(await r.json());
      } catch {}
    }, 2000);
  }
})();
