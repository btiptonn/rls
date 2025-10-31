// js/main.js — GitHub Pages safe
(function () {
  const floorBtn = document.querySelector(".floor-btn");
  let fakeState = "Idle";

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

  // Fake cycle demo
  setInterval(() => {
    const order = ["Idle", "Running", "Aborted", "Complete"];
    fakeState = order[(order.indexOf(fakeState) + 1) % order.length];
    applyStatus(fakeState);
  }, 4000);

  applyStatus(fakeState);
})();
