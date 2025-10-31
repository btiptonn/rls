// js/machine.js
(function () {
  const rfidEl = document.getElementById("rfidStatus");
  const machineEl = document.getElementById("machineState");
  const rgbLedEl = document.getElementById("rgbLed");
  const cycleTimerEl = document.getElementById("cycleTimer");
  const negTimerEl = document.getElementById("negTimer");
  const expectedEl = document.getElementById("expected");
  const logUl = document.getElementById("eventLog");

  let negSeconds = 0;
  let lastRemaining = 0;
  let tickTimer = null;
  let negTimer = null;

  function fmtHMS(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return [h, m, s].map(v => String(v).padStart(2, "0")).join(":");
  }

  function setLed(state, inGrace) {
    // Expect CSS classes: .rgb-led.off/.green/.yellow/.red
    rgbLedEl.classList.remove("off", "green", "yellow", "red");
    if (state === "Running") {
      rgbLedEl.classList.add(inGrace ? "yellow" : "green");
    } else if (state === "Aborted") {
      rgbLedEl.classList.add("red");
    } else if (state === "Complete") {
      rgbLedEl.classList.add("green");
    } else {
      rgbLedEl.classList.add("off");
    }
  }

  function setMachineState(w) {
    // RFID
    rfidEl.textContent = w.rfid ? w.rfid : "Not scanned";
    // Machine state
    machineEl.textContent = w.state;

    // Expected
    expectedEl.textContent = w.expected_min;

    // Remaining & LED
    lastRemaining = Math.max(0, w.remaining_s || 0);
    cycleTimerEl.textContent = fmtHMS(lastRemaining);
    setLed(w.state, w.in_grace);

    // Event log (top N)
    if (Array.isArray(w.log)) {
      logUl.innerHTML = "";
      w.log.slice(0, 20).forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        logUl.appendChild(li);
      });
    }

    // timers
    clearInterval(tickTimer);
    clearInterval(negTimer);
    negSeconds = 0;
    negTimerEl.textContent = String(negSeconds);

    if (w.state === "Running") {
      // decrement the displayed timer each second (front-end only)
      tickTimer = setInterval(() => {
        if (lastRemaining > 0) {
          lastRemaining -= 1;
          cycleTimerEl.textContent = fmtHMS(lastRemaining);
        }
      }, 1000);
    } else if (w.state === "Complete") {
      // start negative timer (how long since it completed)
      negTimer = setInterval(() => {
        negSeconds += 1;
        negTimerEl.textContent = String(negSeconds);
      }, 1000);
    }
  }

  function handleState(w) {
    window.__washer = w;
    setMachineState(w);
  }

  // Prefer SSE
  let usingSSE = false;
  try {
    const es = new EventSource("/api/stream");
    es.addEventListener("init", (e) => { usingSSE = true; handleState(JSON.parse(e.data)); });
    es.addEventListener("state", (e) => handleState(JSON.parse(e.data)));
    es.onerror = () => { /* if it errors, polling fallback below will pick up */ };
  } catch {}

  // Poll fallback every 2s (in case SSE isn’t available)
  setInterval(async () => {
    if (usingSSE) return;
    try {
      const r = await fetch("/api/machines/washer-1/state");
      handleState(await r.json());
    } catch {}
  }, 2000);
})();
