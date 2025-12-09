// --------------------------------------------------------
// MACHINE.JS
// Fetches and updates washer status every second
// --------------------------------------------------------

let cache = {};

function fmt(seconds) {
    if (seconds <= 0) return "0:00";
    let m = Math.floor(seconds / 60);
    let s = seconds % 60;
    return `${m}:${s < 10 ? "0" + s : s}`;
}

async function refreshState() {
    const res = await fetch("/machine/get");
    cache = await res.json();
    updateUI();
}

function updateUI() {
    let s = document.getElementById("state");
    let r = document.getElementById("rfid");
    let t = document.getElementById("time");

    if (s) s.textContent = cache.state;
    if (r) r.textContent = cache.rfid || "None";
    if (t) t.textContent = fmt(cache.remaining_s);

    updateLogs();
}

async function updateLogs() {
    let box = document.getElementById("logbox");
    if (!box) return;

    const logs = await (await fetch("/logs")).json();

    box.innerHTML = logs
        .map(l => `<div>[${l.ts}] <b>${l.event}</b> — ${l.info}</div>`)
        .join("");
}

// auto-run
setInterval(refreshState, 1000);
refreshState();
