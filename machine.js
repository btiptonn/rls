const API = "https://rls-uvzg.onrender.com";

async function getMachine() {
    try {
        let r = await fetch(API + "/machine/get");
        return await r.json();
    } catch (e) {
        console.log("Fetch error:", e);
        return null;
    }
}
