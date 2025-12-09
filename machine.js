const API = "http://172.20.10.9:5000";

async function getMachine() {
    try {
        let res = await fetch(API + "/machine/get");
        return await res.json();
    } catch (e) {
        console.log("Failed fetch", e);
        return null;
    }
}
