// ============================================================
//  RLS MACHINE VIEW — FINAL, DRIFT-FIXED, PERFECTLY SMOOTH
// ============================================================

(function () {

  // DOM
  const stateEl       = document.getElementById("machineState");
  const rfidEl        = document.getElementById("rfidStatus");
  const expectedEl    = document.getElementById("expected");
  const timeEl        = document.getElementById("cycleTimer");
  const negEl         = document.getElementById("negTimer");
  const ledEl         = document.getElementById("rgbLed");
  const logUl         = document.getElementById("eventLog");

  // CONFIG
  const API_BASE  = "https://rls-uvzg.onrender.com";
  const POLL_MS   = 1000;     // poll every 1 sec
  const DRIFT_MAX = 3;        // max drift before hard snap

  // LOCAL STATE
  let localRemaining = 0;
  let backendRemaining = 0;
  let lastUpdateTime = null;
  let machineState = "Idle";
  let negSeconds = 0;

  // LED
  function setLed(color) {
    ledEl.className = "rgb-led " + color;
  }

  // Update Display
  function updateDisplay() {
    stateEl.textContent = machineState;
    rfidEl.textContent = rfidEl.rfid || "None";

    // Expected minutes
    expectedEl.textContent = Math.max(0, Math.floor(backendRemaining / 60));

    // Remaining
    const m = Math.floor(Math.abs(localRemaining) / 60);
    const s = String(Math.abs(localRemaining) % 60).padStart(2, "0");
    timeEl.textContent = `${m}:${s}`;

    negEl.textContent = negSeconds;

    // LED
    if (machineState === "Idle") setLed("off");
    else if (machineState === "Running") setLed("green");
    else if (machineState === "Aborted") setLed("red");
    else if (machineState === "Complete") setLed("yellow");
  }

  // Local 1-second tick
  setInterval(() => {
    if (machineState === "Running") {
      localRemaining -= 1;
    } else if (machineState === "Complete") {
      negSeconds += 1;
    }
    updateDisplay();
  }, 1000);

  // Apply backend
  function applyBackend(data) {
    const serverState = data.state;
    const serverRem   = Number(data.remaining_s);
    const serverLast  = data.last_update ? new Date(data.last_update) : null;

    backendRemaining = serverRem;
    rfidEl.rfid = data.rfid;
    lastUpdateTime = serverLast;

    // State change detection
    if (serverState !== machineState) {
      machineState = serverState;
      prependLog(`${serverState} (RFID: ${data.rfid || "None"})`);
    }

    // Drift correction
    const now = new Date();
    let driftSeconds = 0;

    if (serverLast) {
      driftSeconds = Math.floor((now - serverLast) / 1000);
    }

    const corrected = serverRem - driftSeconds;
    const diff = Math.abs(corrected - localRemaining);

    // Snap if state changed OR drift too big OR first load
    if (machineState !== "Running" || diff > DRIFT_MAX) {
      localRemaining = corrected;
    }

    updateDisplay();
  }

  // Log helper
  function prependLog(msg) {
    if (!logUl) return;
    const li = document.createElement("li");
    li.textContent = `${new Date().toISOString()} — ${msg}`;
    logUl.insertBefore(li, logUl.firstChild);
  }

  // Poll server
  async function poll() {
    try {
      const r = await fetch(`${API_BASE}/api/state`, { cache: "no-store" });
      if (!r.ok) return;

      const data = await r.json();
      applyBackend(data);

      // Get log for UI
      const r2 = await fetch(`${API_BASE}/api/log`, { cache: "no-store" });
      if (r2.ok) {
        const logs = await r2.json();
        logUl.innerHTML = logs.map(l => (
          `<li>[${l.ts}] ${l.event} (state: ${l.state}, RFID: ${l.rfid})</li>`
        )).join("");
      }
    } catch (e) {
      console.error("POLL ERROR:", e);
    }
  }

  // Start polling
  poll();
  setInterval(poll, POLL_MS);

})();
