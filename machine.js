// =======================================================
// MACHINE.JS — All logic combined
// =======================================================

let cache = {};

function fmt(seconds) {
    if (seconds <= 0) return "0:00";
    let m = Math.floor(seconds / 60);
    let s = seconds % 60;
    return m + ":" + (s < 10 ? "0" + s : s);
}

// =======================================================
// FETCH STATE
// =======================================================
async function refreshState() {
    const res = await fetch("/machine/get");
    cache = await res.json();

    updateUI();
}

// =======================================================
// UPDATE UI
// =======================================================
function updateUI() {
    const ids = ["state", "rfid", "time"];
    ids.forEach(id => {
        let el = document.getElementById(id);
        if (!el) return;

        if (id === "state") el.textContent = cache.state;
        if (id === "rfid") el.textContent = cache.rfid || "None";
        if (id === "time") el.textContent = fmt(cache.remaining_s);
    });

    updateLogs();
}

async function updateLogs() {
    let box = document.getElementById("logbox");
    if (!box) return;

    const res = await fetch("/logs");
    const logs = await res.json();

    box.innerHTML = logs.map(l =>
        `<div>[${l.ts}] <b>${l.event}</b> — ${l.info}</div>`
    ).join("");
}

// =======================================================
// START CYCLE
// =======================================================
async function startCycle(mins) {
    const rfid = prompt("Enter RFID (or leave blank):") || null;

    await fetch("/machine/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ minutes: mins, rfid: rfid })
    });

    refreshState();
}

// =======================================================
// RESET
// =======================================================
async function resetWasher() {
    await fetch("/machine/reset", {
        method: "POST"
    });

    refreshState();
}

// =======================================================
// AUTO REFRESH EVERY SECOND
// =======================================================
setInterval(refreshState, 1000);
refreshState();
