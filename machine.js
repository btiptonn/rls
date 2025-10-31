// js/machine.js — GitHub Pages safe
(function () {
  const rfidEl = document.getElementById("rfidStatus");
  const machineEl = document.getElementById("machineState");
  const rgbLedEl = document.getElementById("rgbLed");
  const cycleTimerEl = document.getElementById("cycleTimer");
  const negTimerEl = document.getElementById("negTimer");
  const expectedEl = document.getElementById("expected");
  const logUl = document.getElementById("eventLog");

  function setLed(color) {
    rgbLedEl.className = `rgb-led ${color}`;
  }

  let state = "Idle";
  let remaining = 1800; // 30 min
  let neg = 0;
  let tick;

  function updateDisplay() {
    machineEl.textContent = state;
    rfidEl.textContent = state === "Idle" ? "Not scanned" : "TAG1234";
    expectedEl.textContent = (remaining / 60).toFixed(0);
    const m = Math.floor(Math.abs(remaining) / 60);
    const s = String(Math.abs(remaining) % 60).padStart(2, "0");
    cycleTimerEl.textContent = `${m}:${s}`;
    negTimerEl.textContent = neg;

    if (state === "Idle") setLed("off");
    else if (state === "Running") setLed("green");
    else if (state === "Aborted") setLed("red");
    else if (state === "Complete") setLed("yellow");

    logUl.innerHTML = `<li>${new Date().toLocaleTimeString()} — ${state}</li>` + logUl.innerHTML;
  }

  setInterval(() => {
    const order = ["Idle", "Running", "Aborted", "Complete"];
    state = order[(order.indexOf(state) + 1) % order.length];
    remaining = 1800;
    neg = 0;
    clearInterval(tick);
    if (state === "Running") {
      tick = setInterval(() => {
        remaining--;
        if (remaining <= 0) clearInterval(tick);
        updateDisplay();
      }, 1000);
    } else if (state === "Complete") {
      tick = setInterval(() => {
        neg++;
        updateDisplay();
      }, 1000);
    }
    updateDisplay();
  }, 8000);

  updateDisplay();
})();
