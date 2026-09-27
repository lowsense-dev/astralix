/* © LowSense, 2026 · astralix Userbot · GNU AGPLv3 */
"use strict";
window.AstralixTunnel = {
  async connect(params) {
    const storageKey = "astralix.login.resume.v2", tokenPattern = /^[a-zA-Z0-9_-]{43}$/;
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(storageKey)); } catch {}
    const linkId = params.get("id");
    if (linkId && saved?.id !== linkId) {
      const resume = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))))
        .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
      saved = {id: linkId, ticket: params.get("ticket"), secret: params.get("secret"),
        resume, next: 0, expires: Date.now() + 900000};
    }
    if (!saved || !/^[a-zA-Z0-9_-]{24}$/.test(saved.id || "") ||
        ![saved.ticket, saved.secret, saved.resume].every(value => tokenPattern.test(value || "")) ||
        !Number.isSafeInteger(saved.next) || saved.next < 0 || !Number.isFinite(saved.expires)) throw {status: 401};
    const forget = () => sessionStorage.removeItem(storageKey);
    if (saved.expires <= Date.now()) { forget(); throw {status: 410}; }
    const persist = () => sessionStorage.setItem(storageKey, JSON.stringify(saved));
    // Only the tab's temporary tunnel capability is stored, never API credentials,
    // phone codes or passwords. Closing the tab or completing login discards it.
    persist();
    const sid = saved.id;
    const bytes = Uint8Array.from(atob(saved.secret.replace(/-/g, "+").replace(/_/g, "/") + "="), c => c.charCodeAt(0));
    const encoder = new TextEncoder(), decoder = new TextDecoder("utf-8", {fatal: true});
    const master = await crypto.subtle.importKey("raw", bytes, "HKDF", false, ["deriveKey"]);
    bytes.fill(0);
    const derive = direction => crypto.subtle.deriveKey({name: "HKDF", hash: "SHA-256", salt: new Uint8Array(32), info: encoder.encode("astralix-login-v1:" + direction)}, master, {name: "AES-GCM", length: 256}, false, ["encrypt", "decrypt"]);
    const sendKey = await derive("request"), receiveKey = await derive("response");
    let socket = null, pending = null, ready = false, opening = null, leaving = false;
    const fail = () => {
      if (pending) { clearTimeout(pending.timer); pending.reject({status: 503}); pending = null; }
    };
    const receive = async event => {
      const current = pending;
      if (!current) { socket.close(); return; }
      try {
        const frame = JSON.parse(event.data);
        if (frame.seq !== current.seq || typeof frame.data !== "string" || frame.data.length > 16384) throw new Error();
        const nonce = new Uint8Array(12); new DataView(nonce.buffer).setUint32(8, frame.seq);
        const ciphertext = Uint8Array.from(atob(frame.data), c => c.charCodeAt(0));
        const raw = await crypto.subtle.decrypt({name: "AES-GCM", iv: nonce, additionalData: encoder.encode(sid + ":response:" + frame.seq)}, receiveKey, ciphertext);
        const reply = JSON.parse(decoder.decode(raw));
        if (pending !== current) return;
        clearTimeout(current.timer); pending = null;
        if (reply.result?.stage === "done") forget();
        if (reply.status >= 400) current.reject(reply);
        else current.resolve(reply.result);
      } catch { fail(); socket.close(); }
    };
    async function establish() {
      for (let attempt = 0; attempt < 6; attempt++) {
        if (leaving) throw {status: 503};
        if (Date.now() >= saved.expires) { forget(); throw {status: 410}; }
        const candidate = new WebSocket((location.protocol === "https:" ? "wss:" : "ws:") + "//" + location.host + "/v1/connect");
        try {
          await new Promise((resolve, reject) => {
            const timer = setTimeout(() => { candidate.close(); reject({status: 503}); }, 65000);
            const rejectConnection = status => { clearTimeout(timer); candidate.close(); reject({status}); };
            candidate.onopen = () => candidate.send(JSON.stringify({role: "browser", id: sid,
              token: saved.ticket, protocol: 2, resume: saved.resume}));
            candidate.onerror = candidate.onclose = () => rejectConnection(503);
            candidate.onmessage = event => {
              try {
                const hello = JSON.parse(event.data);
                if (hello.error === "unauthorized") { rejectConnection(401); return; }
                if (hello.error === "busy") { rejectConnection(503); return; }
                if (hello.ready !== true || !Number.isSafeInteger(hello.seq) || hello.seq < 0 || hello.seq > 4096) throw new Error();
                saved.next = Math.max(saved.next, hello.seq);
                persist(); clearTimeout(timer);
                socket = candidate; ready = true;
                candidate.onmessage = receive;
                candidate.onclose = candidate.onerror = () => {
                  if (socket === candidate) { ready = false; fail(); }
                };
                resolve();
              } catch { rejectConnection(401); }
            };
          });
          return;
        } catch (error) {
          if (error.status === 401) { forget(); throw error; }
          if (attempt === 5) throw error;
          await new Promise(resolve => setTimeout(resolve, Math.min(500 * 2 ** attempt, 5000)));
        }
      }
    }
    async function ensureConnected() {
      if (ready) return;
      if (!opening) opening = establish().finally(() => { opening = null; });
      await opening;
    }
    await ensureConnected();
    window.addEventListener("pagehide", () => { leaving = true; socket?.close(); }, {once: true});
    setTimeout(() => { forget(); socket?.close(); }, Math.max(0, saved.expires - Date.now()));
    return {
      async request(path, data) {
        await ensureConnected();
        if (pending) throw {status: 409};
        if (saved.next >= 4096 || Date.now() >= saved.expires) { forget(); throw {status: 410}; }
        const count = saved.next++;
        // Burn a nonce before encryption, even if send fails or the page reloads.
        persist();
        let resolve, reject;
        const result = new Promise((yes, no) => { resolve = yes; reject = no; });
        pending = {seq: count, resolve, reject, timer: setTimeout(() => { fail(); socket.close(); }, 55000)};
        try {
          const nonce = new Uint8Array(12); new DataView(nonce.buffer).setUint32(8, count);
          const raw = encoder.encode(JSON.stringify(data === undefined ? {path} : {path, data}));
          if (raw.length > 4096) throw new Error();
          const encrypted = await crypto.subtle.encrypt({name: "AES-GCM", iv: nonce, additionalData: encoder.encode(sid + ":request:" + count)}, sendKey, raw);
          if (leaving || !ready) throw new Error();
          socket.send(JSON.stringify({seq: count, data: btoa(String.fromCharCode(...new Uint8Array(encrypted)))}));
        } catch { fail(); socket.close(); }
        return result;
      },
    };
  },
};
