// machine.js — smooth countdown using last_update drift correction
(function () {

  const API_BASE = "https://rls-uvzg.onrender.com";
  const POLL_MS = 2000; // poll server every 2s

  // DOM
  const stateEl    = document.getElementById("machineState");
  const rfidEl     = document.getElementById("rfidStatus");
  const timeEl     = document.getElementById("cycleTimer");
  const expectedEl = document.getElementById("expected");
  const negEl      = document.getElementById("negTimer");
  const rgbEl      = document.getElementById("rgbLed");
  const logUl      = document.getElementById("eventLog");

  let lastData = null;
  let lastState = null;

  function setLed(color) {
    rgbEl.className = `rgb-led ${color}`;
  }

  function render() {
    if (!lastData) return;

    const sState = lastData.state;
    const sRFID  = lastData.rfid || "None";
    const sExp   = lastData.expected;
    const sTime  = lastData.time;    // "MM:SS"
    const sLU    = lastData.last_update;

    // parse "MM:SS"
    let [m, s] = sTime.split(":").map(Number);
    let serverRemaining = (m * 60) + s;

    // compute age of snapshot
    const age = Math.floor((Date.now() - new Date(sLU).getTime()) / 1000);
    let adjusted = serverRemaining - age;
    if (adjusted < 0) adjusted = 0;

    // Show negative timer only if complete
    const neg = (sState === "Complete") ? age : 0;

    // Log state changes
    if (sState !== lastState) {
      if (logUl) {
        const li = document.createElement("li");
        li.textContent = `[${new Date().toLocaleTimeString()}] ${sState} — RFID: ${sRFID}`;
        logUl.insertBefore(li, logUl.firstChild);
      }
      lastState = sState;
    }

    // Update DOM
    stateEl.textContent = sState;
    rfidEl.textContent = sRFID;
    expectedEl.textContent = sExp;
    negEl.textContent = neg;

    const mm = Math.floor(adjusted / 60);
    const ss = String(adjusted % 60).padStart(2, "0");
    timeEl.textContent = `${mm}:${ss}`;

    if (sState === "Idle") setLed("off");
    else if (sState === "Running") setLed("green");
    else if (sState === "Aborted") setLed("red");
    else if (sState === "Complete") setLed("yellow");
  }

  async function poll() {
    try {
      const res = await fetch(`${API_BASE}/api/state`, { cache: "no-store" });
      if (!res.ok) return;
      lastData = await res.json();
      render();
    } catch (err) {
      console.error("poll error:", err);
    }
  }

  // Poll every 2 sec
  poll();
  setInterval(poll, POLL_MS);

})();
