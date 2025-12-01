// js/machine.js — smooth countdown + gentle sync with backend
(function () {
  // ---- DOM ELEMENTS ----
  const rfidEl       = document.getElementById("rfidStatus");
  const machineEl    = document.getElementById("machineState");
  const rgbLedEl     = document.getElementById("rgbLed");
  const cycleTimerEl = document.getElementById("cycleTimer");
  const negTimerEl   = document.getElementById("negTimer");
  const expectedEl   = document.getElementById("expected");
  const logUl        = document.getElementById("eventLog");

  // ---- CONFIG ----
  const API_BASE   = "https://rls-uvzg.onrender.com";
  const MACHINE_ID = "pico-w-laundry-01";   // <-- your real device_id
  const POLL_MS    = 3000;                  // poll server every 3s
  const CORRECTION_THRESHOLD = 15;          // only snap if > 15s off

  // ---- LOCAL STATE ----
  let state = "Idle";
  let remainingSeconds = 0;
  let negativeSeconds  = 0;
  let expectedMinutes  = 0;
  let rfid             = "None";

  let lastServerState  = null;

  // ---- HELPERS ----
  function setLed(color) {
    rgbLedEl.className = `rgb-led ${color}`;
  }

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

  function logEvent(msg) {
    if (!logUl) return;
    const li = document.createElement("li");
    li.textContent = `${new Date().toISOString()} ${msg}`;
    logUl.insertBefore(li, logUl.firstChild);
  }

  // ---- 1-SECOND LOCAL TICK (UI ONLY) ----
  setInterval(() => {
    if (state === "Running" && remainingSeconds > 0) {
      remainingSeconds -= 1;
    } else if (state === "Complete") {
      negativeSeconds += 1;
    }
    updateDisplay();
  }, 1000);

  // ---- APPLY SERVER SNAPSHOT (EVERY 3s) ----
  function applyServerStatus(data) {
    // These keys should match what your Pico POSTs
    const serverState     = data.state || "Idle";
    const serverRemaining = Number(data.remaining_seconds ?? 0);
    const serverNegative  = Number(data.overtime_seconds ?? 0);
    const serverRFID      = data.rfid || "None";

    // Log state changes
    if (serverState !== lastServerState) {
      logEvent(`state: ${serverState}, RFID: ${serverRFID}`);
      lastServerState = serverState;
    }

    // --- SMART SYNC LOGIC ---
    if (serverState === "Running") {
      if (state !== "Running") {
        // just entered Running → trust server completely
        remainingSeconds = serverRemaining;
      } else {
        // already running → only correct if way off
        const diff = Math.abs(serverRemaining - remainingSeconds);
        if (diff > CORRECTION_THRESHOLD) {
          remainingSeconds = serverRemaining;
        }
        // if diff is small (like 3–4s), ignore it so UI stays smooth
      }
    } else {
      // not running (Idle / Aborted / Complete) → always trust server
      remainingSeconds = serverRemaining;
    }

    // update other fields
    state = serverState;
    negativeSeconds = serverNegative;
    expectedMinutes = Math.ceil(serverRemaining / 60);
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

  // start everything
  updateDisplay();
  pollStatus();
  setInterval(pollStatus, POLL_MS);
})();
