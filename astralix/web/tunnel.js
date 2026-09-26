/* © LowSense, 2026 · astralix Userbot · GNU AGPLv3 */
"use strict";
window.AstralixTunnel = {
  async connect(params) {
    const sid = params.get("id"), ticket = params.get("ticket");
    let secret = params.get("secret");
    if (!/^[a-zA-Z0-9_-]{24}$/.test(sid || "") || !/^[a-zA-Z0-9_-]{43}$/.test(ticket || "") || !/^[a-zA-Z0-9_-]{43}$/.test(secret || "")) throw {status: 401};
    const bytes = Uint8Array.from(atob(secret.replace(/-/g, "+").replace(/_/g, "/") + "="), c => c.charCodeAt(0));
    const encoder = new TextEncoder(), decoder = new TextDecoder("utf-8", {fatal: true});
    const master = await crypto.subtle.importKey("raw", bytes, "HKDF", false, ["deriveKey"]);
    bytes.fill(0); secret = null;
    const derive = direction => crypto.subtle.deriveKey({name: "HKDF", hash: "SHA-256", salt: new Uint8Array(32), info: encoder.encode(`astralix-login-v1:${direction}`)}, master, {name: "AES-GCM", length: 256}, false, ["encrypt", "decrypt"]);
    const sendKey = await derive("request"), receiveKey = await derive("response");
    const socket = new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/v1/connect`);
    let pending = null, seq = 0, ready = false;
    const fail = () => {
      if (pending) { clearTimeout(pending.timer); pending.reject({status: 410}); pending = null; }
    };
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { socket.close(); reject({status: 410}); }, 15000);
      socket.onopen = () => socket.send(JSON.stringify({role: "browser", id: sid, token: ticket}));
      socket.onerror = socket.onclose = () => { clearTimeout(timer); reject({status: 410}); };
      socket.onmessage = event => {
        try {
          if (JSON.parse(event.data).ready !== true) throw new Error();
          clearTimeout(timer); ready = true; resolve();
        } catch { clearTimeout(timer); socket.close(); reject({status: 401}); }
      };
    });
    socket.onclose = socket.onerror = () => { ready = false; fail(); };
    socket.onmessage = async event => {
      const current = pending;
      if (!current) { socket.close(); return; }
      try {
        const frame = JSON.parse(event.data);
        if (frame.seq !== current.seq || typeof frame.data !== "string" || frame.data.length > 16384) throw new Error();
        const nonce = new Uint8Array(12); new DataView(nonce.buffer).setUint32(8, frame.seq);
        const ciphertext = Uint8Array.from(atob(frame.data), c => c.charCodeAt(0));
        const raw = await crypto.subtle.decrypt({name: "AES-GCM", iv: nonce, additionalData: encoder.encode(`${sid}:response:${frame.seq}`)}, receiveKey, ciphertext);
        const reply = JSON.parse(decoder.decode(raw));
        if (pending !== current) return;
        clearTimeout(current.timer); pending = null;
        if (reply.status >= 400) current.reject(reply);
        else current.resolve(reply.result);
      } catch { fail(); socket.close(); }
    };
    window.addEventListener("pagehide", () => socket.close(), {once: true});
    return {
      async request(path, data) {
        if (!ready || pending || seq >= 128) throw {status: 410};
        const count = seq++;
        let resolve, reject;
        const result = new Promise((yes, no) => { resolve = yes; reject = no; });
        pending = {seq: count, resolve, reject, timer: setTimeout(() => { fail(); socket.close(); }, 55000)};
        try {
          const nonce = new Uint8Array(12); new DataView(nonce.buffer).setUint32(8, count);
          const raw = encoder.encode(JSON.stringify(data === undefined ? {path} : {path, data}));
          if (raw.length > 4096) throw new Error();
          const encrypted = await crypto.subtle.encrypt({name: "AES-GCM", iv: nonce, additionalData: encoder.encode(`${sid}:request:${count}`)}, sendKey, raw);
          socket.send(JSON.stringify({seq: count, data: btoa(String.fromCharCode(...new Uint8Array(encrypted)))}));
        } catch { fail(); socket.close(); }
        return result;
      },
    };
  },
};
