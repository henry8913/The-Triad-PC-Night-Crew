function getItem(key) {
  try {
    return globalThis.localStorage ? globalThis.localStorage.getItem(key) : null;
  } catch {
    return null;
  }
}

function setItem(key, value) {
  try {
    if (!globalThis.localStorage) return false;
    globalThis.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function removeItem(key) {
  try {
    if (!globalThis.localStorage) return false;
    globalThis.localStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}

async function share({ title, text, url }) {
  const u = url || globalThis.location?.href || "";
  const payload = { title: title || "", text: text || "", url: u };

  try {
    if (globalThis.navigator?.share) {
      await globalThis.navigator.share(payload);
      return { ok: true, method: "share" };
    }
  } catch {
  }

  try {
    if (globalThis.navigator?.clipboard?.writeText) {
      await globalThis.navigator.clipboard.writeText(u);
      return { ok: true, method: "clipboard" };
    }
  } catch {
  }

  try {
    globalThis.prompt("Copia il link:", u);
    return { ok: true, method: "prompt" };
  } catch {
    return { ok: false, method: "none" };
  }
}

globalThis.ncStorage = { getItem, setItem, removeItem };
globalThis.ncShare = { share };

function scrollToBottom(elementId) {
  try {
    const el = globalThis.document?.getElementById(elementId);
    if (!el) return false;
    el.scrollTop = el.scrollHeight;
    return true;
  } catch {
    return false;
  }
}

function scrollToMessageStart(containerId, messageId) {
  try {
    const container = globalThis.document?.getElementById(containerId);
    const message = globalThis.document?.getElementById(messageId);
    if (!container || !message) return false;

    const containerRect = container.getBoundingClientRect();
    const messageRect = message.getBoundingClientRect();
    const delta = messageRect.top - containerRect.top;
    container.scrollTop = Math.max(0, container.scrollTop + delta - 8);
    return true;
  } catch {
    return false;
  }
}

globalThis.ncChat = { scrollToBottom, scrollToMessageStart };
