/* © radiocycle, 2026 · astralix Userbot · GNU AGPLv3
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
      ready: "Можно закрыть эту вкладку", privacy: "Данные отправляются только в твой экземпляр astralix и Telegram.", private: "Личное подключение",
      continue: "Продолжить", send: "Получить код", connect: "Подключить аккаунт", wait: "Подожди немного…",
      loading: ["Подключаемся…", "Проверяем ссылку для входа."],
      api: ["Начнём с приложения", "Введи API ID и hash своего приложения Telegram. Это нужно только при первом запуске."],
      phone: ["Добро пожаловать домой", "Укажи номер своего аккаунта Telegram. Отправим на него код подтверждения."],
      code: ["Проверь свой Telegram", "Введи код входа, который прислал Telegram. Никому его не передавай."],
      password: ["Ещё один шаг", "У тебя включена двухэтапная аутентификация. Введи облачный пароль, чтобы завершить вход."],
      done: ["Ты на своей орбите", "Аккаунт подключён. astralix завершает настройку и запускает userbot."],
      locked: ["Нужна ссылка для входа", "Открой приватную ссылку из терминала, в котором запущен astralix. Если она истекла — перезапусти приложение."],
      errors: {code: "Неверный код. Проверь сообщение от Telegram и попробуй ещё раз.", password: "Неверный облачный пароль.", phone: "Telegram не принял этот номер. Проверь код страны и цифры.", api: "Telegram не принял API ID/hash. Проверь данные приложения.", expired: "Код истёк. Запроси новый код.", flood: "Слишком много попыток. Подожди перед повтором.", network: "Нет ответа от Telegram. Проверь соединение и попробуй снова.", internal: "Не удалось завершить шаг. Попробуй снова или используй консольный вход с --no-web.", bad: "Проверь формат введённых данных.", conflict: "Этот шаг уже изменился. Обнови страницу.", unavailable: "Не удалось связаться с astralix. Проверь, что он запущен и SSH-туннель открыт."},
    },
    en: {
      eyebrow: "YOUR OWN LITTLE UNIVERSE", hero1: "Your Telegram.", hero2: "In your own orbit.",
      heroCopy: "Connect your account. Let astralix take it from here.", setup: "CONNECT YOUR ACCOUNT",
      apiLink: "Get credentials at my.telegram.org ↗", phoneLabel: "Phone number", phoneHint: "Include the country code, e.g. +79991234567",
      codeLabel: "Verification code", codeHint: "Check your Telegram service messages.", passwordLabel: "Cloud password",
      passwordHint: "Your Telegram two-step verification password.", show: "Show", hide: "Hide",
      ready: "You can close this tab", privacy: "Your details are sent only to your own astralix instance and Telegram.", private: "Private connection",
      continue: "Continue", send: "Send verification code", connect: "Connect account", wait: "Just a moment…",
      loading: ["Connecting…", "Checking your private sign-in link."],
      api: ["Start with your app", "Enter your Telegram application's API ID and hash. You'll only need to do this once."],
      phone: ["Welcome to your space", "Enter the phone number of your Telegram account. We'll send you a verification code."],
      code: ["Check your Telegram", "Enter the login code sent by Telegram. Keep it to yourself."],
      password: ["One more step", "Two-step verification is enabled. Enter your cloud password to finish signing in."],
      done: ["You're in your own orbit", "Account connected. astralix is finishing setup and starting your userbot."],
      locked: ["A private link is needed", "Open the private link from the terminal running astralix. If it has expired, restart the application."],
      errors: {code: "Invalid code. Check the Telegram message and try again.", password: "Incorrect cloud password.", phone: "Telegram rejected this number. Check the country code and digits.", api: "Telegram rejected the API ID/hash. Check your app credentials.", expired: "The code expired. Request a new one.", flood: "Too many attempts. Please wait before trying again.", network: "Telegram did not respond. Check your connection and retry.", internal: "Couldn't complete this step. Retry or use console login with --no-web.", bad: "Check the format of the details you entered.", conflict: "This step has already changed. Refresh the page.", unavailable: "Cannot reach astralix. Check that it is running and your SSH tunnel is open."},
    },
  };
  let locale = navigator.language.startsWith("ru") ? "ru" : "en";
  let stage = "loading", csrf = "", busy = false, errorKey = "", retrySeconds = 0;
  const stages = ["api", "phone", "code", "password"];
  function render(focus = false) {
    const t = copy[locale];
    document.documentElement.lang = locale;
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t[el.dataset.i18n]; });
    $("locale").textContent = locale === "ru" ? "EN ↗" : "RU ↗";
    $("form-title").textContent = t[stage][0];
    $("form-description").textContent = t[stage][1];
    const index = stages.indexOf(stage);
    $("step-count").textContent = stage === "done" ? "04 / 04" : index < 0 ? "— / 04" : `0${index + 1} / 04`;
    document.querySelectorAll(".progress i").forEach((el, i) => el.classList.toggle("active", stage === "done" || i <= index));
    stages.forEach((item) => {
      const fields = $(`${item}-fields`);
      fields.hidden = item !== stage;
      fields.querySelectorAll("input").forEach((input) => { input.disabled = item !== stage || busy; input.required = item === stage; });
    });
    $("login-form").hidden = index < 0;
    $("completion").hidden = stage !== "done";
    $("step-icon").textContent = ({done: "✓", locked: "⌁", password: "✳", code: "#"})[stage] || "↗";
    $("submit-label").textContent = busy ? t.wait : stage === "phone" ? t.send : stage === "password" ? t.connect : t.continue;
    $("submit").disabled = busy;
    $("login-form").setAttribute("aria-busy", String(busy));
    $("notice").hidden = !errorKey;
    $("notice").textContent = errorKey ? (t.errors[errorKey] || t.errors.internal) + (retrySeconds ? ` (${retrySeconds}s)` : "") : "";
    $("reveal").textContent = $("password").type === "password" ? t.show : t.hide;
    if (focus && index >= 0) $(`${stage}-fields`).querySelector("input").focus();
  }
  async function api(path, data) {
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
      if (stages.includes(error.result?.stage)) stage = error.result.stage;
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
  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || !stages.includes(stage)) return;
    const data = Object.fromEntries(new FormData(event.target));
    busy = true; errorKey = ""; retrySeconds = 0; render();
    try {
      const result = await api("/api/step", data);
      if (stages.includes(result.stage) || result.stage === "done") stage = result.stage;
    } catch (error) { handleError(error); }
    finally {
      // No credentials in storage or in retained form fields after submission.
      for (const id of ["api-hash", "code", "password"]) $(id).value = "";
      $("password").type = "password"; $("reveal").setAttribute("aria-pressed", "false");
      busy = false; render(true);
    }
  });
  async function init() {
    let key = new URLSearchParams(location.hash.slice(1)).get("key");
    history.replaceState(null, "", location.pathname);
    render();
    try {
      if (key) await api("/api/unlock", {key});
      key = null;
      const state = await api("/api/state");
      csrf = state.csrf;
      stage = stages.includes(state.stage) || state.stage === "done" ? state.stage : "locked";
    } catch (error) { handleError(error); if (stage === "loading") stage = "locked"; }
    finally { key = null; render(true); }
  }
  init();
})();
