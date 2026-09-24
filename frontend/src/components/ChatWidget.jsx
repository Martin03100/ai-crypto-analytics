import { AlertCircle, History, MessageCircle, Plus, Send, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useConfirm } from "../context/ConfirmContext";
import { useToast } from "../context/ToastContext";
import { useProviders } from "../context/ProvidersContext";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";

const CONVERSATIONS_KEY = "aca_chat_conversations";
const MAX_CONVERSATIONS = 20;
const PROVIDER_LABELS = {
  gemini: "Gemini",
  openai: "OpenAI (ChatGPT)",
  anthropic: "Anthropic (Claude)",
  deepseek: "DeepSeek",
  grok: "Grok (xAI)",
};

/** Kazda konverzacia: { id, title, messages: [...], updatedAt } */
function loadConversations() {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversations(conversations) {
  try {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations.slice(0, MAX_CONVERSATIONS)));
  } catch {
    // localStorage plny / nedostupny — historia sa proste neulozi pre tuto relaciu
  }
}

function makeTitle(firstMessage, fallback) {
  const text = (firstMessage || fallback).trim();
  return text.length > 42 ? `${text.slice(0, 39)}...` : text;
}

export default function ChatWidget() {
  const { push } = useToast();
  const { t, lang } = useLanguage();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const providersCtx = useProviders();
  const providers = providersCtx.providers;
  const [provider, setProvider] = useState(null);
  const [conversations, setConversations] = useState(loadConversations);
  const [activeId, setActiveId] = useState(() => conversations[0]?.id || null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);
  const locale = localeForLang(lang);
  const newConvTitle = t("chat.newConversationTitle");

  const active = conversations.find((c) => c.id === activeId) || null;
  const messages = active?.messages || [];

  useEffect(() => {
    if (providersCtx.defaultProvider) setProvider(providersCtx.defaultProvider);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providersCtx.defaultProvider]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length, sending]);

  const activeConnected = providers.find((p) => p.provider === provider)?.connected;

  function updateConversation(id, updater) {
    setConversations((prev) => {
      const next = prev.map((c) => (c.id === id ? updater(c) : c));
      saveConversations(next);
      return next;
    });
  }

  function startNewConversation() {
    const id = `conv-${Date.now()}`;
    const fresh = { id, title: newConvTitle, messages: [], updatedAt: Date.now() };
    setConversations((prev) => {
      const next = [fresh, ...prev];
      saveConversations(next);
      return next;
    });
    setActiveId(id);
    setShowHistory(false);
  }

  async function deleteConversation(id) {
    const ok = await confirm(t("chat.deleteConfirm"));
    if (!ok) return;
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      saveConversations(next);
      if (activeId === id) setActiveId(next[0]?.id || null);
      return next;
    });
  }

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    if (!provider) {
      push(t("chat.selectProviderWarning"), "warn");
      return;
    }

    let conv = active;
    if (!conv) {
      conv = { id: `conv-${Date.now()}`, title: newConvTitle, messages: [], updatedAt: Date.now() };
      setConversations((prev) => {
        const next = [conv, ...prev];
        saveConversations(next);
        return next;
      });
      setActiveId(conv.id);
    }

    const userMsg = { role: "user", content: text, ts: Date.now() };
    const nextMessages = [...conv.messages, userMsg];
    const isFirstMessage = conv.messages.length === 0;
    updateConversation(conv.id, (c) => ({
      ...c, messages: nextMessages, updatedAt: Date.now(),
      title: isFirstMessage ? makeTitle(text, newConvTitle) : c.title,
    }));
    setInput("");
    setSending(true);
    try {
      const res = await api.sendChatMessage(provider, nextMessages.map(({ role, content }) => ({ role, content })));
      if (res.success && res.data) {
        const assistantMsg = {
          role: "assistant", content: res.data.reply, tokens: res.data.tokens_used,
          cost: res.data.estimated_cost_usd, isMock: res.is_mock, ts: Date.now(),
        };
        updateConversation(conv.id, (c) => ({ ...c, messages: [...c.messages, assistantMsg], updatedAt: Date.now() }));
      } else {
        push(res.error_message || t("chat.sendFailed"), "error");
      }
    } catch (err) {
      push(err, "error");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <>
      <button className="fab-chat" title={t("chat.title")} onClick={() => setOpen((v) => !v)}>
        {open ? <X size={22} /> : <MessageCircle size={22} />}
      </button>

      {open && (
        <div className="chat-drawer">
          <div className="chat-drawer-header">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <MessageCircle size={16} />
              <strong style={{ fontSize: 13.5 }}>{t("chat.title")}</strong>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowHistory((v) => !v)} title={t("chat.historyTooltip")}>
                <History size={13} />
              </button>
              <button className="btn btn-ghost btn-sm" onClick={startNewConversation} title={t("chat.newTooltip")}>
                <Plus size={13} />
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)} aria-label={t("chat.closeChat")}>
                <X size={13} />
              </button>
            </div>
          </div>

          {showHistory ? (
            <div className="chat-history-list">
              {conversations.length === 0 && <p className="text-sub" style={{ padding: 12 }}>{t("chat.noConversations")}</p>}
              {conversations.map((c) => (
                <div key={c.id} className={`chat-history-item ${c.id === activeId ? "active" : ""}`}
                     onClick={() => { setActiveId(c.id); setShowHistory(false); }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="chat-history-title">{c.title}</div>
                    <div className="chat-history-date">{new Date(c.updatedAt).toLocaleString(locale)}</div>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); deleteConversation(c.id); }} aria-label={t("chat.deleteConversation")}>
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="chat-drawer-toolbar">
                <select
                  className="select"
                  value={provider || ""}
                  onChange={(e) => setProvider(e.target.value)}
                  style={{ fontSize: 12.5, padding: "6px 8px" }}
                >
                  {providers.length === 0 && <option value="">{t("chat.providerLoading")}</option>}
                  {providers.map((p) => (
                    <option key={p.provider} value={p.provider} disabled={!p.connected}>
                      {PROVIDER_LABELS[p.provider] || p.label}{!p.connected ? t("chat.missingKeySuffix") : ""}
                    </option>
                  ))}
                </select>
                {!activeConnected && provider && (
                  <div className="chat-key-warning">
                    <AlertCircle size={12} /> {t("chat.missingKeyWarning")}
                  </div>
                )}
              </div>

              <div className="chat-drawer-messages" ref={scrollRef}>
                {messages.length === 0 && (
                  <p className="text-sub" style={{ padding: "8px 2px" }}>
                    {t("chat.emptyState")}
                  </p>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`chat-bubble ${m.role}`}>
                    <div>{m.content}</div>
                    {m.role === "assistant" && (m.tokens || m.cost !== undefined) && (
                      <div className="chat-meta">
                        {m.isMock && <span className="badge badge-mock" style={{ marginRight: 6 }}>{t("badge.mock")}</span>}
                        {t("chat.tokensAndCost", { tokens: m.tokens, cost: (m.cost || 0).toFixed(4) })}
                      </div>
                    )}
                  </div>
                ))}
                {sending && <div className="chat-bubble assistant chat-typing">{t("chat.thinking")}</div>}
              </div>

              <div className="chat-drawer-input">
                <textarea
                  className="input"
                  rows={1}
                  placeholder={t("chat.placeholder")}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  style={{ resize: "none", flex: 1 }}
                />
                <button className="btn btn-primary btn-sm" onClick={send} disabled={sending || !input.trim()} aria-label={t("chat.sendMessage")}>
                  <Send size={14} />
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
