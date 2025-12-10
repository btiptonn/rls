const API = "http://rls-uvzg.onrender.com/";

async function getMachine() {
    try {
        let res = await fetch(API + "/machine/get");
        return await res.json();
    } catch (e) {
        console.log("Failed fetch", e);
        return null;
    }
}

