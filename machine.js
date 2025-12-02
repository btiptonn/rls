// machine.js — Correct client for /api/state
(function () {

  const API_BASE = "https://rls-uvzg.onrender.com";
  const POLL_MS = 1000; // check server every second

  // DOM
  const stateEl = document.getElementById("machineState");
  const rfidEl = document.getElementById("rfidStatus");
  const timeEl = document.getElementById("cycleTimer");
  const expectedEl = document.getElementById("expected");
  const negEl = document.getElementById("negTimer");
  const logUl = document.getElementById("eventLog");
  const rgbEl = document.getElementById("rgbLed");

  let lastData = null;
  let lastState = null;

  // LED helper
  function setLed(color) {
    rgbEl.className = `rgb-led ${color}`;
  }

  // Render function
  function render() {
    if (!lastData) return;

    const serverState = lastData.state;
    const rfid = lastData.rfid || "None";
    const expected = lastData.expected;
    const timeStr = lastData.time; // "MM:SS"
    const lastUpdate = lastData.last_update;

    // parse "MM:SS" -> seconds
    let [m, s] = timeStr.split(":").map(Number);
    let serverSeconds = m * 60 + s;

    // compute age
    let age = 0;
    if (lastUpdate) {
      const last = new Date(lastUpdate).getTime();
      age = Math.floor((Date.now() - last) / 1000);
    }

    let adjusted = serverSeconds - age;
    if (adjusted < 0) adjusted = 0;

    // format display
    const mm = Math.floor(adjusted / 60);
    const ss = String(adjusted % 60).padStart(2, "0");
    const display = `${mm}:${ss}`;

    // state change log
    if (serverState !== lastState) {
      if (logUl) {
        const li = document.createElement("li");
        li.textContent = `[${new Date().toLocaleTimeString()}] ${serverState} — RFID: ${rfid}`;
        logUl.insertBefore(li, logUl.firstChild);
      }
      lastState = serverState;
    }

    // Update DOM
    stateEl.textContent = serverState;
    rfidEl.textContent = rfid;
    expectedEl.textContent = expected;
    timeEl.textContent = display;
    negEl.textContent = (serverState === "Complete") ? age : 0;

    if (serverState === "Idle") setLed("off");
    else if (serverState === "Running") setLed("green");
    else if (serverState === "Aborted") setLed("red");
    else if (serverState === "Complete") setLed("yellow");
  }

  // Poll backend
  async function poll() {
    try {
      const res = await fetch(`${API_BASE}/api/state`, { cache: "no-store" });
      if (!res.ok) {
        console.log("Server state error:", res.status);
        return;
      }
      lastData = await res.json();
      render();
    } catch (e) {
      console.log("Poll error:", e);
    }
  }

  // Start polling
  poll();
  setInterval(poll, POLL_MS);

})();
