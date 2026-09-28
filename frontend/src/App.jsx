import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(result.detail || `Request failed (${response.status})`);
  }
  return result;
}

function App() {
  const [view, setView] = useState("chat");
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState("");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [adminError, setAdminError] = useState("");
  const [conversations, setConversations] = useState([]);
  const [activity, setActivity] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [adminLoading, setAdminLoading] = useState(false);

  useEffect(() => {
    api("/admin/users")
      .then(({ users: rows }) => {
        setUsers(rows);
        if (rows.length) setUserId((current) => current || rows[0].user_id);
      })
      .catch((requestError) => setError(requestError.message));
  }, []);

  useEffect(() => {
    if (!userId.trim()) {
      setMessages([]);
      return;
    }
    api(`/conversations/${encodeURIComponent(userId.trim())}`)
      .then(({ conversations: rows }) => {
        const transcript = rows.slice().reverse().flatMap((row) => [
          { role: "user", text: row.user_message },
          { role: "assistant", text: row.assistant_response },
        ]);
        setMessages(transcript);
        setError("");
      })
      .catch((requestError) => setError(requestError.message));
  }, [userId]);

  useEffect(() => {
    if (view !== "admin") return;
    setAdminLoading(true);
    setAdminError("");
    Promise.all([api("/admin/conversations"), api("/admin/tool-activity")])
      .then(([conversationResult, activityResult]) => {
        setConversations(conversationResult.conversations);
        setActivity(activityResult.activity);
      })
      .catch((requestError) => setAdminError(requestError.message))
      .finally(() => setAdminLoading(false));
  }, [view]);

  async function sendMessage(event) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !userId.trim() || loading) return;
    setDraft("");
    setError("");
    setMessages((current) => [...current, { role: "user", text: content }]);
    setLoading(true);
    try {
      const result = await api("/chat", {
        method: "POST",
        body: JSON.stringify({ user_id: userId.trim(), message: content }),
      });
      setMessages((current) => [
        ...current,
        { role: "assistant", text: result.response },
      ]);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function openConversation(id) {
    setSelectedConversation(null);
    try {
      setSelectedConversation(await api(`/admin/conversations/${id}`));
    } catch (requestError) {
      setAdminError(requestError.message);
    }
  }

  async function toggleFlag(conversation) {
    try {
      const result = await api(`/admin/conversations/${conversation.conversation_id}/flag`, {
        method: "PATCH",
        body: JSON.stringify({ flagged: !conversation.flagged_for_attention }),
      });
      setConversations((current) => current.map((row) =>
        row.conversation_id === result.conversation_id ? result : row,
      ));
      setSelectedConversation(result);
    } catch (requestError) {
      setAdminError(requestError.message);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#chat" onClick={() => setView("chat")}>
          <span className="brand-mark" aria-hidden="true">P</span>
          <span><strong>Portfolio</strong><small>REAL ESTATE ANALYST</small></span>
        </a>
        <nav className="view-switch" aria-label="Application views">
          <button className={view === "chat" ? "active" : ""} onClick={() => setView("chat")}>Analyst</button>
          <button className={view === "admin" ? "active" : ""} onClick={() => setView("admin")}>Operations</button>
        </nav>
        <span className="connection-label"><i /> Rule-based assistant</span>
      </header>

      {view === "chat" ? (
        <section className="chat-layout">
          <aside className="side-rail">
            <div className="section-kicker">WORKSPACE</div>
            <label className="field-label" htmlFor="user-select">Portfolio owner</label>
            <select id="user-select" value={userId} onChange={(event) => setUserId(event.target.value)}>
              <option value="">Select a user</option>
              {users.map((user) => <option key={user.user_id} value={user.user_id}>{user.name} · {user.user_id}</option>)}
            </select>
            <label className="field-label custom-id-label" htmlFor="user-id">Or enter user ID</label>
            <input id="user-id" value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="e.g. U001" />
            <div className="rail-note">
              <span className="note-dot" />
              <p>Answers use this portfolio's saved records.</p>
            </div>
            <div className="rail-footer">PRIVATE PORTFOLIO VIEW</div>
          </aside>

          <section className="chat-panel" aria-label="Portfolio conversation">
            <div className="chat-heading">
              <div>
                <div className="section-kicker">PORTFOLIO DESK</div>
                <h1>Ask your analyst</h1>
              </div>
              {userId && <span className="owner-chip">{userId}</span>}
            </div>
            <div className="transcript" aria-live="polite">
              {messages.length === 0 && (
                <div className="empty-state">
                  <div className="empty-rule" />
                  <p className="empty-overline">YOUR PORTFOLIO, IN CONTEXT</p>
                  <h2>What would you like to know?</h2>
                  <p>Ask about portfolio value, rental income, a property, or a hypothetical scenario.</p>
                  <div className="prompt-row">
                    <button onClick={() => setDraft("What is my portfolio value?")}>Portfolio value <span>↗</span></button>
                    <button onClick={() => setDraft("Show my portfolio by location")}>By location <span>↗</span></button>
                    <button onClick={() => setDraft("Tell me about property P002")}>Property details <span>↗</span></button>
                  </div>
                </div>
              )}
              {messages.map((message, index) => (
                <article className={`message ${message.role}`} key={`${index}-${message.role}`}>
                  <div className="message-label">{message.role === "user" ? userId || "YOU" : "ANALYST"}</div>
                  <p>{message.text}</p>
                </article>
              ))}
              {loading && <div className="typing"><span /><span /><span /> Analyzing portfolio</div>}
            </div>
            {error && <div className="inline-error" role="alert">{error}</div>}
            <form className="composer" onSubmit={sendMessage}>
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage(event);
                  }
                }}
                placeholder={userId ? "Ask about this portfolio..." : "Select or enter a user ID first"}
                aria-label="Message the analyst"
                disabled={!userId || loading}
                rows="1"
              />
              <button type="submit" aria-label="Send message" disabled={!draft.trim() || !userId || loading}>
                <span>Send</span><b aria-hidden="true">↗</b>
              </button>
            </form>
            <div className="composer-footnote">Actual data is read from your portfolio. Hypothetical results are labeled and do not change it.</div>
          </section>
        </section>
      ) : (
        <section className="admin-page">
          <div className="admin-heading">
            <div>
              <div className="section-kicker">BUSINESS OVERVIEW</div>
              <h1>Operations</h1>
            </div>
            <span className="updated-tag">{adminLoading ? "Refreshing..." : `${users.length} users · ${conversations.length} recent conversations`}</span>
          </div>
          {adminError && <div className="inline-error" role="alert">{adminError}</div>}
          <div className="admin-grid">
            <section className="admin-section users-section">
              <div className="section-title"><h2>Users</h2><span>{users.length}</span></div>
              <div className="user-list">
                {users.map((user) => (
                  <button className="user-row" key={user.user_id} onClick={() => { setUserId(user.user_id); setView("chat"); }}>
                    <span className="avatar">{user.name?.slice(0, 1) || "U"}</span>
                    <span><strong>{user.name}</strong><small>{user.city || "Location not set"}</small></span>
                    <code>{user.user_id}</code>
                  </button>
                ))}
              </div>
            </section>
            <section className="admin-section conversations-section">
              <div className="section-title"><h2>Conversations</h2><span>{conversations.filter((row) => row.flagged_for_attention).length} flagged</span></div>
              <div className="conversation-list">
                {conversations.map((conversation) => (
                  <button
                    className={`conversation-row ${selectedConversation?.conversation_id === conversation.conversation_id ? "selected" : ""}`}
                    key={conversation.conversation_id}
                    onClick={() => openConversation(conversation.conversation_id)}
                  >
                    <span className={`flag-marker ${conversation.flagged_for_attention ? "on" : ""}`} />
                    <span className="conversation-copy"><strong>{conversation.user_message}</strong><small>{conversation.user_id} · {conversation.created_at || "Recent"}</small></span>
                    <span className="row-arrow">↗</span>
                  </button>
                ))}
                {!conversations.length && <p className="quiet-empty">No conversations recorded yet.</p>}
              </div>
            </section>
            <section className="admin-section detail-section">
              <div className="section-title"><h2>Conversation detail</h2></div>
              {selectedConversation ? (
                <div className="detail-content">
                  <div className="detail-meta"><span>{selectedConversation.user_id}</span><span>{selectedConversation.created_at}</span></div>
                  <div className="detail-message"><small>USER</small><p>{selectedConversation.user_message}</p></div>
                  <div className="detail-message assistant-detail"><small>ANALYST</small><p>{selectedConversation.assistant_response}</p></div>
                  <button className="flag-button" onClick={() => toggleFlag(selectedConversation)}>
                    {selectedConversation.flagged_for_attention ? "Remove attention flag" : "Flag for attention"}
                  </button>
                </div>
              ) : <p className="quiet-empty">Select a conversation to inspect its exchange.</p>}
            </section>
            <section className="admin-section activity-section">
              <div className="section-title"><h2>Tool activity</h2><span>Recent</span></div>
              <div className="activity-list">
                {activity.map((entry) => (
                  <div className="activity-row" key={entry.activity_id}>
                    <span className={`activity-status ${entry.succeeded ? "success" : "failure"}`} />
                    <span><strong>{entry.tool_name}</strong><small>{entry.user_id} · {entry.created_at}</small></span>
                  </div>
                ))}
                {!activity.length && <p className="quiet-empty">No tool activity recorded yet.</p>}
              </div>
            </section>
          </div>
        </section>
      )}
    </main>
  );
}

export default App;