// js/machine.js — production version with smooth countdown + API polling
(function () {
  // ---- DOM ELEMENTS ----
  const rfidEl       = document.getElementById("rfidStatus");
  const machineEl    = document.getElementById("machineState");
  const rgbLedEl     = document.getElementById("rgbLed");
  const cycleTimerEl = document.getElementById("cycleTimer");
  const negTimerEl   = document.getElementById("negTimer");
  const expectedEl   = document.getElementById("expected");
  const logUl        = document.getElementById("eventLog");

  // ---- CONFIG: ADJUST TO YOUR BACKEND ----
  // Example: https://rls-uvzg.onrender.com/api/machines/washer-1
  const API_BASE   = "https://rls-uvzg.onrender.com";
  const MACHINE_ID = "washer-1"; // change if needed
  const POLL_MS    = 3000;       // how often we poll server
  const DRIFT_MAX  = 4;          // seconds of allowed drift before snap-to-server

  // ---- LOCAL STATE ----
  let state = "Idle";
  let remainingSeconds = 0;   // time left in the cycle
  let negativeSeconds  = 0;   // overtime after complete
  let expectedMinutes  = 0;   // expected total time (for display)
  let rfid             = "None";
  let lastServerState  = null;
  let lastServerRemaining = null;

  function setLed(color) {
    rgbLedEl.className = `rgb-led ${color}`;
  }

  // ---- DISPLAY UPDATE ----
  function updateDisplay() {
    machineEl.textContent = state;
    rfidEl.textContent = rfid || "None";
    expectedEl.textContent = expectedMinutes;

    const absRem = Math.max(0, Math.abs(remainingSeconds));
    const m = Math.floor(absRem / 60);
    const s = String(absRem % 60).padStart(2, "0");
    cycleTimerEl.textContent = `${m}:${s}`;

    negTimerEl.textContent = negativeSeconds;

    if (state === "Idle") setLed("off");
    else if (state === "Running") setLed("green");
    else if (state === "Aborted") setLed("red");
    else if (state === "Complete") setLed("yellow");
    else setLed("off");
  }

  // ---- EVENT LOGGING (ONLY WHEN STATE CHANGES) ----
  function logEvent(msg) {
    if (!logUl) return;
    const li = document.createElement("li");
    li.textContent = `${new Date().toISOString()} ${msg}`;
    logUl.insertBefore(li, logUl.firstChild);
  }

  // ---- LOCAL TICK (SMOOTH UI) ----
  setInterval(() => {
    if (state === "Running" && remainingSeconds > 0) {
      remainingSeconds -= 1;
    } else if (state === "Complete") {
      negativeSeconds += 1;
    }
    updateDisplay();
  }, 1000);

  // ---- APPLY SERVER STATUS WITH DRIFT CORRECTION ----
  function applyServerStatus(data) {
    // Adjust these field names to match your real JSON keys
    const serverState          = data.state || "Idle";
    const serverRemaining      = Number(data.remaining_seconds ?? data.remaining ?? 0);
    const serverNegative       = Number(data.overtime_seconds ?? data.neg_seconds ?? 0);
    const serverExpectedMin    = Number(data.expected_minutes ?? Math.ceil(serverRemaining / 60));
    const serverRFID           = data.rfid || data.lock_owner_uid || "None";

    // Log state changes
    if (serverState !== lastServerState) {
      logEvent(`state: ${serverState}, RFID: ${serverRFID}`);
      lastServerState = serverState;
    }

    // Drift correction: only snap if big disagreement
    const diff = Math.abs(serverRemaining - remainingSeconds);
    if (lastServerRemaining === null || diff > DRIFT_MAX || serverState !== state) {
      remainingSeconds = serverRemaining;
      lastServerRemaining = serverRemaining;
    }

    state = serverState;
    negativeSeconds = serverNegative;
    expectedMinutes = serverExpectedMin;
    rfid = serverRFID;

    updateDisplay();
  }

  // ---- POLL BACKEND ----
  async function pollStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/machines/${MACHINE_ID}`, {
        cache: "no-store"
      });
      if (!res.ok) {
        console.error("Status fetch failed:", res.status);
        return;
      }
      const data = await res.json();
      applyServerStatus(data);
    } catch (err) {
      console.error("Error polling status:", err);
    }
  }

  // Start polling
  pollStatus();
  setInterval(pollStatus, POLL_MS);

  // Initial paint
  updateDisplay();
})();
