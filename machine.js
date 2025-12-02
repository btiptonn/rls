// js/machine.js — read snapshot + drift-correct using last_update
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
  const MACHINE_ID = "pico-w-laundry-01";
  const POLL_MS    = 2000;   // ask server every 2s

  let latestData = null;
  let lastState  = null;

  function setLed(color) {
    rgbLedEl.className = `rgb-led ${color}`;
  }

  function logEvent(msg) {
    if (!logUl) return;
    const li = document.createElement("li");
    li.textContent = `${new Date().toISOString()} ${msg}`;
    logUl.insertBefore(li, logUl.firstChild);
  }

  function render() {
    if (!latestData) return;

    const state       = latestData.state || "Idle";
    const remServer   = Number(latestData.remaining_seconds ?? 0);
    const overtime    = Number(latestData.overtime_seconds ?? 0);
    const rfid        = latestData.rfid || "None";
    const lastUpdate  = latestData.last_update;

    // compute how old the snapshot is
    let remNow = remServer;
    if (lastUpdate) {
      const lastMs = new Date(lastUpdate).getTime();
      const nowMs  = Date.now();
      const ageSec = Math.floor((nowMs - lastMs) / 1000);
      remNow = remServer - ageSec;
    }
    if (remNow < 0) remNow = 0;

    if (state !== lastState) {
      logEvent(`state: ${state}, RFID: ${rfid}`);
      lastState = state;
    }

    const m = Math.floor(remNow / 60);
    const s = String(remNow % 60).padStart(2, "0");
    cycleTimerEl.textContent = `${m}:${s}`;
    negTimerEl.textContent = overtime;
    expectedEl.textContent = Math.ceil(remServer / 60);

    machineEl.textContent = state;
    rfidEl.textContent = rfid;

    if (state === "Idle") setLed("off");
    else if (state === "Running") setLed("green");
    else if (state === "Aborted") setLed("red");
    else if (state === "Complete") setLed("yellow");
    else setLed("off");
  }

  async function pollStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/machines/${MACHINE_ID}`, {
        cache: "no-store",
      });
      if (!res.ok) {
        console.error("Status fetch failed:", res.status);
        return;
      }
      latestData = await res.json();
      render();
    } catch (err) {
      console.error("Error polling status:", err);
    }
  }

  // initial render & start loop
  pollStatus();
  setInterval(pollStatus, POLL_MS);
})();
