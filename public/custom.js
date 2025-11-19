// public/custom.js

(() => {
  let isComposing = false;
  let enterCount = 0;
  let lastEnterTime = 0;
  const ENTER_THRESHOLD_MS = 1000;

  const isEditable = (el) => {
    if (!el || !(el instanceof Element)) return false;
    if (el.tagName === "TEXTAREA") return true;
    if (el.isContentEditable) return true;
    if (el.tagName === "INPUT") {
      const type = (el.getAttribute("type") || "text").toLowerCase();
      return ["text","search","url","tel","email","password"].includes(type);
    }
    return false;
  };

  const insertNewlineInTextControl = (el) => {
    if (!("selectionStart" in el) || !("value" in el)) return false;
    const start = el.selectionStart;
    const end   = el.selectionEnd;
    const v     = el.value;
    const next  = v.slice(0, start) + "\n" + v.slice(end);
    el.value     = next;
    const pos    = start + 1;
    el.selectionStart = el.selectionEnd = pos;
    const ev    = new Event("input", { bubbles: true });
    el.dispatchEvent(ev);
    return true;
  };

  const insertLineBreakCE = () => {
    try {
      if (document.queryCommandSupported && document.queryCommandSupported("insertLineBreak")) {
        document.execCommand("insertLineBreak");
        return true;
      }
    } catch (_){}
    const sel = window.getSelection?.();
    if (!sel || !sel.rangeCount) return false;
    const range = sel.getRangeAt(0);
    range.deleteContents();
    const br = document.createElement("br");
    range.insertNode(br);
    range.setStartAfter(br);
    range.setEndAfter(br);
    sel.removeAllRanges();
    sel.addRange(range);
    return true;
  };

  const clickSubmitButton = async () => {
    const selectors = [
      '#chat-submit',
      'button[type="submit"]',
      'button[aria-label*="send" i]',
      '[data-testid="submit-button"]'
    ];
    for (const selector of selectors) {
      let btn = document.querySelector(selector);
      if (!btn) {
        // retry after short delay
        await new Promise(r => setTimeout(r, 100));
        btn = document.querySelector(selector);
      }
      if (btn && !btn.disabled) {
        console.log("[Custom JS] 找到送出按鈕: ", selector, btn);
        btn.click();
        return true;
      }
    }
    console.log("[Custom JS] ❌ 無法找到送出按鈕");
    return false;
  };

  const detectLanguage = (text) => {
    if (!text || text.trim().length === 0) return "empty";
    const chineseCount = (text.match(/[\u4e00-\u9fff\u3400-\u4dbf]/g) || []).length;
    const totalChars   = text.replace(/\s+/g, '').length;
    if (totalChars === 0) return "empty";
    if (chineseCount / totalChars > 0.2) return "chinese";
    return "english";
  };

  const handleEnter = async (e) => {
    if (e.key !== "Enter") return;
    if (e.isComposing || isComposing) return;

    const now = Date.now();
    const tgt = e.target;

    if (isEditable(tgt)) {
      e.preventDefault();
      e.stopImmediatePropagation();
      e.stopPropagation();

      const inputText = tgt.value || tgt.textContent || "";
      const language  = detectLanguage(inputText);

      console.log(`[Custom JS] 檢測到語言: ${language}, 文本長度: ${inputText.length}`);

      if (language === "chinese") {
        if (now - lastEnterTime < ENTER_THRESHOLD_MS) {
          enterCount += 1;
        } else {
          enterCount = 1;
        }
        lastEnterTime = now;

        if (enterCount >= 2) {
          console.log("[Custom JS] 中文 - 兩次 Enter，準備送出訊息");
          const ok = await clickSubmitButton();
          enterCount = 0;
          if (!ok) {
            if (tgt.isContentEditable) {
              insertLineBreakCE();
            } else {
              insertNewlineInTextControl(tgt);
            }
          }
        } else {
          console.log("[Custom JS] 中文 - 一次 Enter，插入換行");
          if (tgt.isContentEditable) {
            insertLineBreakCE();
          } else {
            insertNewlineInTextControl(tgt);
          }
        }
      } else {
        console.log("[Custom JS] 英文/其他 - 一次 Enter，準備送出訊息");
        const ok = await clickSubmitButton();
        if (!ok) {
          if (tgt.isContentEditable) {
            insertLineBreakCE();
          } else {
            insertNewlineInTextControl(tgt);
          }
        }
      }
      return;
    }
  };

  const attachCompositionHandlers = (el) => {
    el.addEventListener("compositionstart", () => { isComposing = true; }, { capture: true, passive: true });
    el.addEventListener("compositionend",   () => { isComposing = false; }, { capture: true, passive: true });
  };

  const bindInputs = (root = document) => {
    const sel = [
      'div[contenteditable="true"]',
      'textarea',
      'input[type="text"]',
      'input[type="search"]',
      'input[type="url"]',
      'input[type="tel"]',
      'input[type="email"]',
      'input[type="password"]'
    ].join(',');
    root.querySelectorAll(sel).forEach(attachCompositionHandlers);
  };

  const blockFormSubmit = (root = document) => {
    root.querySelectorAll("form").forEach((f) => {
      f.addEventListener("submit", (e) => {
        e.preventDefault();
        e.stopImmediatePropagation();
        e.stopPropagation();
      }, { capture: true });
    });
  };

  const attachGlobalKeyGuards = () => {
    ["keydown","keypress","keyup"].forEach(type => {
      document.addEventListener(type, handleEnter, { capture: true });
      window.addEventListener(type, handleEnter, { capture: true });
    });
  };

  const patchAddEventListener = () => {
    const orig = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function(type, listener, options){
      if ((type === "keydown" || type === "keypress" || type === "keyup")
          && typeof listener === "function") {
        const wrapped = function(ev){
          if (ev && ev.key === "Enter" && !ev.defaultPrevented) {
            return;
          }
          return listener.call(this, ev);
        };
        try { (listener.__wrappedListeners ||= new WeakMap()).set(this, wrapped); } catch(_){}
        return orig.call(this, type, wrapped, options);
      }
      return orig.call(this, type, listener, options);
    };
    const origRemove = EventTarget.prototype.removeEventListener;
    EventTarget.prototype.removeEventListener = function(type, listener, options){
      const wrapped = listener?.__wrappedListeners?.get?.(this);
      return origRemove.call(this, type, wrapped || listener, options);
    };
  };

  const init = () => {
    console.log("[Custom JS] ✅ 已加載 - 自訂 Enter 行為");
    attachGlobalKeyGuards();
    patchAddEventListener();
    bindInputs(document);
    blockFormSubmit(document);

    const mo = new MutationObserver((muts) => {
      for (const m of muts) {
        if (m.type === "childList" && m.addedNodes?.length) {
          m.addedNodes.forEach((n) => {
            if (n.nodeType === 1) {
              bindInputs(n);
              blockFormSubmit(n);
            }
          });
        }
      }
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
