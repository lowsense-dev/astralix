/* © LowSense, 2026 · GNU AGPLv3 */
"use strict";
const root = document.documentElement;
const localeButton = document.querySelector(".locale");
let language = navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en";
try { const saved = localStorage.getItem("astralix-language"); if (saved === "ru" || saved === "en") language = saved; } catch {}
function setLanguage(value) {
  language = value;
  root.lang = value;
  root.dataset.lang = value;
  localeButton.textContent = value === "ru" ? "EN ↗" : "RU ↗";
  localeButton.setAttribute("aria-label", value === "ru" ? "Switch to English" : "Переключить на русский");
}
setLanguage(language);
localeButton.addEventListener("click", () => {
  setLanguage(language === "ru" ? "en" : "ru");
  try { localStorage.setItem("astralix-language", language); } catch {}
});
document.querySelectorAll(".copy").forEach(button => {
  button.addEventListener("click", async () => {
    const text = button.closest(".code").querySelector("code").textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = language === "ru" ? "Скопировано ✓" : "Copied ✓";
      document.querySelector("#status").textContent = button.textContent;
    } catch {
      const range = document.createRange();
      range.selectNodeContents(button.closest(".code").querySelector("code"));
      const selection = window.getSelection();
      selection.removeAllRanges(); selection.addRange(range);
      button.textContent = language === "ru" ? "Нажми Ctrl/Cmd+C" : "Press Ctrl/Cmd+C";
    }
    window.setTimeout(() => { button.textContent = language === "ru" ? "Копировать" : "Copy"; }, 2500);
  });
});

