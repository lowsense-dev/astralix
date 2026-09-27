/* © LowSense, 2026 · astralix Userbot · GNU AGPLv3
   https://github.com/lowsense-dev/astralix */
"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const copy = {
    ru: {
      eyebrow: "YOUR OWN LITTLE UNIVERSE", hero1: "Твой Telegram.", hero2: "На твоей орбите.",
      heroCopy: "Подключи аккаунт — остальное возьмёт на себя astralix.", setup: "ПОДКЛЮЧЕНИЕ АККАУНТА",
      apiLink: "Получить на my.telegram.org ↗", phoneLabel: "Номер телефона", phoneHint: "С кодом страны, например +79991234567",
      codeLabel: "Код подтверждения", codeHint: "Проверь сервисные сообщения Telegram.", passwordLabel: "Облачный пароль",
      passwordHint: "Пароль двухэтапной аутентификации Telegram.", show: "Показать", hide: "Скрыть",
      qrButton: "Войти по QR-коду", qrHint: "Открой Telegram → Настройки → Устройства → Подключить устройство и отсканируй код.", qrAria: "QR-код для входа в Telegram",
      ready: "Можно закрыть эту вкладку", privacy: "Данные отправляются только в твой экземпляр astralix и Telegram.", private: "Личное подключение",
      continue: "Продолжить", send: "Получить код", connect: "Подключить аккаунт", wait: "Подожди немного…",
      loading: ["Подключаемся…", "Проверяем ссылку для входа."],
      api: ["Начнём с приложения", "Введи API ID и hash своего приложения Telegram. Это нужно только при первом запуске."],
      phone: ["Добро пожаловать домой", "Укажи номер своего аккаунта Telegram. Отправим на него код подтверждения."],
      code: ["Проверь свой Telegram", "Введи код входа, который прислал Telegram. Никому его не передавай."],
      qr: ["Отсканируй QR-код", "Подтверди вход с устройства, где Telegram уже авторизован."],
      password: ["Ещё один шаг", "У тебя включена двухэтапная аутентификация. Введи облачный пароль, чтобы завершить вход."],
      done: ["Ты на своей орбите", "Аккаунт подключён. astralix завершает настройку и запускает userbot."],
      locked: ["Нужна ссылка для входа", "Открой приватную ссылку из терминала, в котором запущен astralix. Если она истекла — перезапусти приложение."],
      errors: {code: "Неверный код. Проверь сообщение от Telegram и попробуй ещё раз.", password: "Неверный облачный пароль.", phone: "Telegram не принял этот номер. Проверь код страны и цифры.", api: "Telegram не принял API ID/hash. Проверь данные приложения.", expired: "Код истёк. Запроси новый код.", flood: "Слишком много попыток. Подожди перед повтором.", network: "Нет ответа от Telegram. Проверь соединение и попробуй снова.", internal: "Не удалось завершить шаг. Попробуй снова или используй консольный вход с --no-web.", bad: "Проверь формат введённых данных.", conflict: "Этот шаг уже изменился. Обнови страницу.", unavailable: "Не удалось связаться с astralix. Проверь соединение. Если туннель закрылся, запусти вход заново и открой новую ссылку."},
    },
    en: {
      eyebrow: "YOUR OWN LITTLE UNIVERSE", hero1: "Your Telegram.", hero2: "In your own orbit.",
      heroCopy: "Connect your account. Let astralix take it from here.", setup: "CONNECT YOUR ACCOUNT",
      apiLink: "Get credentials at my.telegram.org ↗", phoneLabel: "Phone number", phoneHint: "Include the country code, e.g. +79991234567",
      codeLabel: "Verification code", codeHint: "Check your Telegram service messages.", passwordLabel: "Cloud password",
      passwordHint: "Your Telegram two-step verification password.", show: "Show", hide: "Hide",
      qrButton: "Sign in with QR code", qrHint: "Open Telegram → Settings → Devices → Link Desktop Device and scan the code.", qrAria: "QR code for Telegram sign-in",
      ready: "You can close this tab", privacy: "Your details are sent only to your own astralix instance and Telegram.", private: "Private connection",
      continue: "Continue", send: "Send verification code", connect: "Connect account", wait: "Just a moment…",
      loading: ["Connecting…", "Checking your private sign-in link."],
      api: ["Start with your app", "Enter your Telegram application's API ID and hash. You'll only need to do this once."],
      phone: ["Welcome to your space", "Enter the phone number of your Telegram account. We'll send you a verification code."],
      code: ["Check your Telegram", "Enter the login code sent by Telegram. Keep it to yourself."],
      qr: ["Scan the QR code", "Confirm sign-in from a device where Telegram is already authorized."],
      password: ["One more step", "Two-step verification is enabled. Enter your cloud password to finish signing in."],
      done: ["You're in your own orbit", "Account connected. astralix is finishing setup and starting your userbot."],
      locked: ["A private link is needed", "Open the private link from the terminal running astralix. If it has expired, restart the application."],
      errors: {code: "Invalid code. Check the Telegram message and try again.", password: "Incorrect cloud password.", phone: "Telegram rejected this number. Check the country code and digits.", api: "Telegram rejected the API ID/hash. Check your app credentials.", expired: "The code expired. Request a new one.", flood: "Too many attempts. Please wait before trying again.", network: "Telegram did not respond. Check your connection and retry.", internal: "Couldn't complete this step. Retry or use console login with --no-web.", bad: "Check the format of the details you entered.", conflict: "This step has already changed. Refresh the page.", unavailable: "Cannot reach astralix. Check the connection. If the tunnel closed, restart login and open the new link."},
    },
  };
  let locale = navigator.language.startsWith("ru") ? "ru" : "en";
  let stage = "loading", csrf = "", busy = false, errorKey = "", retrySeconds = 0, qr = null, qrPolling = false;
  let secureMode = false, secureSendKey = null, secureReceiveKey = null, resumeKey = null;
  const secureStorageKey = "astralix.login.encryption.v1";
  const stages = ["api", "phone", "code", "password"];
  const validStages = [...stages, "qr"];
  const encode = (bytes) => btoa(String.fromCharCode(...bytes));
  const decode = (value) => Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
  async function setSecureKey(value) {
    const bytes = decode(value.replace(/-/g, "+").replace(/_/g, "/") + "=");
    if (bytes.length !== 32) throw {status: 401};
    try {
      const master = await crypto.subtle.importKey("raw", bytes, "HKDF", false, ["deriveKey"]);
      const derive = (direction) => crypto.subtle.deriveKey({
        name: "HKDF", hash: "SHA-256", salt: new Uint8Array(32),
        info: new TextEncoder().encode(`astralix-login-v1:${direction}`),
      }, master, {name: "AES-GCM", length: 256}, false, ["encrypt", "decrypt"]);
      [secureSendKey, secureReceiveKey] = await Promise.all([derive("request"), derive("response")]);
    } finally {
      bytes.fill(0);
    }
    secureMode = true;
  }
  function clearSecureKey() {
    sessionStorage.removeItem(secureStorageKey);
    secureSendKey = secureReceiveKey = null;
    resumeKey = null;
    secureMode = false;
  }
  function drawQr(code) {
    if (!code || !Number.isInteger(code.size) || code.size < 21 || code.size > 177 || typeof code.data !== "string") return;
    const bytes = Uint8Array.from(atob(code.data), (char) => char.charCodeAt(0));
    if (bytes.length * 8 < code.size ** 2) return;
    const canvas = $("qr-code"), scale = 4;
    canvas.width = canvas.height = code.size * scale;
    const context = canvas.getContext("2d");
    context.fillStyle = "#fff"; context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#10120f";
    for (let offset = 0; offset < code.size ** 2; offset++) {
      if (bytes[offset >> 3] & (1 << (7 - offset % 8))) context.fillRect(offset % code.size * scale, Math.floor(offset / code.size) * scale, scale, scale);
    }
  }
  function applyState(result) {
    if (validStages.includes(result.stage) || result.stage === "done") stage = result.stage;
    qr = stage === "qr" ? result.qr : null;
  }
  function render(focus = false) {
    const t = copy[locale];
    document.documentElement.lang = locale;
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t[el.dataset.i18n]; });
    $("locale").textContent = locale === "ru" ? "EN ↗" : "RU ↗";
    $("form-title").textContent = t[stage][0];
    $("form-description").textContent = t[stage][1];
    const index = stage === "qr" ? 2 : stages.indexOf(stage);
    $("step-count").textContent = stage === "done" ? "04 / 04" : index < 0 ? "— / 04" : `0${index + 1} / 04`;
    document.querySelectorAll(".progress i").forEach((el, i) => el.classList.toggle("active", stage === "done" || i <= index));
    stages.forEach((item) => {
      const fields = $(`${item}-fields`);
      fields.hidden = item !== stage;
      fields.querySelectorAll("input").forEach((input) => { input.disabled = item !== stage || busy; input.required = item === stage; });
    });
    $("login-form").hidden = !stages.includes(stage);
    $("qr-start").hidden = stage !== "phone";
    $("qr-start").disabled = busy;
    $("qr-panel").hidden = stage !== "qr";
    $("qr-code").setAttribute("aria-label", t.qrAria);
    if (stage === "qr") drawQr(qr);
    $("completion").hidden = stage !== "done";
    $("step-icon").textContent = ({done: "✓", locked: "⌁", password: "✳", code: "#", qr: "▦"})[stage] || "↗";
    $("submit-label").textContent = busy ? t.wait : stage === "phone" ? t.send : stage === "password" ? t.connect : t.continue;
    $("submit").disabled = busy;
    $("login-form").setAttribute("aria-busy", String(busy));
    $("notice").hidden = !errorKey;
    $("notice").textContent = errorKey ? (t.errors[errorKey] || t.errors.internal) + (retrySeconds ? ` (${retrySeconds}s)` : "") : "";
    $("reveal").textContent = $("password").type === "password" ? t.show : t.hide;
    if (focus && stages.includes(stage)) $(`${stage}-fields`).querySelector("input").focus();
  }
  async function api(path, data) {
    if (secureMode) {
      const nonce = crypto.getRandomValues(new Uint8Array(12));
      const payload = new TextEncoder().encode(JSON.stringify(data === undefined ? {path} : {path, data}));
      const encrypted = await crypto.subtle.encrypt(
        {name: "AES-GCM", iv: nonce, additionalData: new TextEncoder().encode("astralix-login-v1")},
        secureSendKey, payload,
      );
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 55000);
      try {
        const response = await fetch("/api/secure", {
          method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({iv: encode(nonce), data: encode(new Uint8Array(encrypted))}),
          signal: controller.signal,
        });
        if (!response.ok) throw {status: response.status};
        const frame = await response.json();
        const raw = await crypto.subtle.decrypt(
          {name: "AES-GCM", iv: decode(frame.iv), additionalData: new TextEncoder().encode("astralix-login-v1")},
          secureReceiveKey, decode(frame.data),
        );
        const reply = JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(raw));
        if (!Number.isInteger(reply.status) || !reply.result || typeof reply.result !== "object") throw new Error();
        if (reply.status >= 400) throw {status: reply.status, result: reply.result};
        return reply.result;
      } catch (error) {
        if (Number.isInteger(error.status)) throw error;
        throw {status: 503};
      } finally {
        clearTimeout(timeout);
      }
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 55000);
    try {
      const response = await fetch(path, {
        method: data === undefined ? "GET" : "POST", credentials: "same-origin", cache: "no-store", signal: controller.signal,
        headers: data === undefined ? {} : {"Content-Type": "application/json", "X-CSRF-Token": csrf},
        body: data === undefined ? undefined : JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw {status: response.status, result};
      return result;
    } finally { clearTimeout(timeout); }
  }
  function handleError(error) {
    const status = error.status;
    if ([401, 403, 410].includes(status)) { stage = "locked"; errorKey = ""; }
    else {
      if (validStages.includes(error.result?.stage)) stage = error.result.stage;
      errorKey = status === 429 ? "flood" : error.result?.error;
      if (!copy.en.errors[errorKey]) errorKey = status === 400 ? "bad" : status === 409 ? "conflict" : "unavailable";
      retrySeconds = Number(error.result?.retry_after) || 0;
    }
  }
  $("locale").addEventListener("click", () => { locale = locale === "ru" ? "en" : "ru"; render(); });
  $("reveal").addEventListener("click", () => {
    const visible = $("password").type === "password";
    $("password").type = visible ? "text" : "password";
    $("reveal").setAttribute("aria-pressed", String(visible)); render();
  });
  async function submitStep(data) {
    if (busy) return;
    busy = true; errorKey = ""; retrySeconds = 0; render();
    try {
      const result = await api("/api/step", data);
      applyState(result);
      if (stage === "done") clearSecureKey();
    } catch (error) { handleError(error); }
    finally {
      // No credentials in storage or in retained form fields after submission.
      for (const id of ["api-hash", "code", "password"]) $(id).value = "";
      $("password").type = "password"; $("reveal").setAttribute("aria-pressed", "false");
      busy = false; render(true);
      if (stage === "qr") pollQr();
    }
  }
  $("login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (stages.includes(stage)) submitStep(Object.fromEntries(new FormData(event.target)));
  });
  $("qr-start").addEventListener("click", () => submitStep({qr: "start"}));
  async function pollQr() {
    if (qrPolling) return;
    qrPolling = true;
    while (stage === "qr") {
      try {
        applyState(await api("/api/step", {qr: "poll"}));
        errorKey = ""; retrySeconds = 0;
      } catch (error) { handleError(error); break; }
      render();
    }
    qrPolling = false;
  }
  async function init() {
    const params = new URLSearchParams(location.hash.slice(1));
    let key = params.get("key");
    try {
      if (key && params.get("secure") === "1") {
        await setSecureKey(key);
        resumeKey = key;
        sessionStorage.setItem(secureStorageKey, JSON.stringify({
          origin: location.origin, key, expires: Date.now() + 900000,
        }));
      } else if (!key) {
        const saved = JSON.parse(sessionStorage.getItem(secureStorageKey) || "null");
        if (saved?.origin === location.origin && Number.isFinite(saved.expires) && saved.expires > Date.now()) {
          await setSecureKey(saved.key);
          resumeKey = saved.key;
        } else if (saved) clearSecureKey();
      }
    } catch {
      clearSecureKey();
      key = null;
    }
    history.replaceState(null, "", location.pathname);
    render();
    try {
      if (key) await api("/api/unlock", {key});
      else if (secureMode && resumeKey) {
        try { await api("/api/unlock", {key: resumeKey}); }
        catch (error) { if (error.status !== 401) throw error; }
      }
      key = null;
      const state = await api("/api/state");
      csrf = state.csrf;
      applyState(state);
      if (!validStages.includes(stage) && stage !== "done") stage = "locked";
      if (stage === "done") clearSecureKey();
    } catch (error) { handleError(error); if (stage === "loading") stage = "locked"; }
    finally { key = null; params.delete("key"); render(true); if (stage === "qr") pollQr(); }
  }
  init();
})();
