import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "▦" },
  { id: "chat", label: "AI Analyst", icon: "✳" },
  { id: "properties", label: "Properties", icon: "⌂" },
  { id: "admin", label: "Operations", icon: "◎" },
];
const CURRENCY = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

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

function formatMoney(value) {
  return value == null ? "Data not available" : CURRENCY.format(Number(value));
}

function LoadingState({ label = "Loading portfolio data" }) {
  return <div className="loading-state" role="status"><span className="spinner" />{label}</div>;
}

function EmptyState({ title, children }) {
  return <div className="quiet-empty"><strong>{title}</strong>{children && <p>{children}</p>}</div>;
}

function StatusBadge({ children, tone = "neutral" }) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}

function KpiCard({ label, value, note, icon }) {
  return (
    <article className="kpi-card">
      <div className="kpi-top"><span>{label}</span><span className="kpi-icon" aria-hidden="true">{icon}</span></div>
      <strong className="kpi-value">{value}</strong>
      <span className="kpi-note">{note}</span>
    </article>
  );
}

function OwnerPicker({ users, userId, usersLoading, onChange, includeManualInput = false, mobile = false }) {
  const selectId = mobile ? "mobile-user-select" : "user-select";
  const knownOwner = users.some((user) => user.user_id === userId);

  return (
    <div className={mobile ? "mobile-owner-picker" : "sidebar-owner"}>
      <label htmlFor={selectId}>Portfolio owner</label>
      <select id={selectId} value={userId} onChange={(event) => onChange(event.target.value)}>
        <option value="">{usersLoading ? "Loading owners..." : users.length ? "Choose a saved portfolio" : "No saved owners available"}</option>
        {userId && !knownOwner && <option value={userId}>Entered ID · {userId}</option>}
        {users.map((user) => <option key={user.user_id} value={user.user_id}>{user.name || "Portfolio owner"}{user.city ? ` · ${user.city}` : ""} · {user.user_id}</option>)}
      </select>
      {includeManualInput && <>
        <label className="custom-id-label" htmlFor="user-id">Or enter user ID</label>
        <input id="user-id" value={userId} onChange={(event) => onChange(event.target.value)} placeholder="Enter user ID" />
      </>}
    </div>
  );
}

function PropertyForm({ property, busy, error, onClose, onSubmit }) {
  const [form, setForm] = useState(() => ({
    property_type: property?.property_type || "",
    sub_type: property?.sub_type || "",
    location: property?.location || "",
    area_sqft: property?.area_sqft ?? "",
    current_estimated_value_inr: property?.current_estimated_value_inr ?? "",
    purchase_price_inr: property?.purchase_price_inr ?? "",
    annual_rent_inr: property?.annual_rent_inr ?? "",
    occupancy_status: property?.occupancy_status || "",
    tenant_status: property?.tenant_status || "",
    ownership_percent: property?.ownership_percent ?? "",
    status: property?.status || "",
  }));

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="property-modal" role="dialog" aria-modal="true" aria-labelledby="property-form-title">
        <div className="modal-heading">
          <div><div className="section-kicker">PORTFOLIO RECORD</div><h2 id="property-form-title">{property ? `Edit ${property.property_id}` : "Add property"}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close property form">×</button>
        </div>
        {error && <div className="inline-error" role="alert">{error}</div>}
        <form className="property-form" onSubmit={(event) => onSubmit(event, form)}>
          {!property && <div className="form-field"><label htmlFor="property-type">Property type</label><select id="property-type" name="property_type" value={form.property_type} onChange={updateField} required><option value="">Select type</option><option>Residential</option><option>Commercial</option><option>Industrial</option></select></div>}
          {!property && <div className="form-field"><label htmlFor="property-subtype">Subtype</label><input id="property-subtype" name="sub_type" value={form.sub_type} onChange={updateField} required /></div>}
          <div className="form-field form-wide"><label htmlFor="property-location">Location</label><input id="property-location" name="location" value={form.location} onChange={updateField} required /></div>
          <div className="form-field"><label htmlFor="property-area">Area (sq ft)</label><input id="property-area" name="area_sqft" type="number" min="0.01" step="any" value={form.area_sqft} onChange={updateField} required /></div>
          <div className="form-field"><label htmlFor="property-value">Current estimated value (INR)</label><input id="property-value" name="current_estimated_value_inr" type="number" min="0" step="any" value={form.current_estimated_value_inr} onChange={updateField} required={!property} /></div>
          <div className="form-field"><label htmlFor="property-purchase">Purchase price (INR)</label><input id="property-purchase" name="purchase_price_inr" type="number" min="0" step="any" value={form.purchase_price_inr} onChange={updateField} /></div>
          <div className="form-field"><label htmlFor="property-rent">Annual rent (INR)</label><input id="property-rent" name="annual_rent_inr" type="number" min="0" step="any" value={form.annual_rent_inr} onChange={updateField} required={!property} /></div>
          <div className="form-field"><label htmlFor="property-occupancy">Occupancy</label><select id="property-occupancy" name="occupancy_status" value={form.occupancy_status} onChange={updateField} required><option value="">Select status</option><option>Occupied</option><option>Vacant</option><option>Under construction</option></select></div>
          <div className="form-field"><label htmlFor="property-tenant">Tenant status</label><input id="property-tenant" name="tenant_status" value={form.tenant_status} onChange={updateField} required={!property} /></div>
          <div className="form-field"><label htmlFor="property-ownership">Ownership (%)</label><input id="property-ownership" name="ownership_percent" type="number" min="0.01" max="100" step="any" value={form.ownership_percent} onChange={updateField} required={!property} /></div>
          <div className="form-field"><label htmlFor="property-status">Property status</label><input id="property-status" name="status" value={form.status} onChange={updateField} required={!property} /></div>
          <div className="form-actions form-wide"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" type="submit" disabled={busy}>{busy ? "Saving..." : property ? "Save changes" : "Add property"}</button></div>
        </form>
      </section>
    </div>
  );
}

function PropertyTable({ properties, onEdit }) {
  if (!properties.length) return <EmptyState title="No properties found">Property records for this portfolio will appear here.</EmptyState>;
  return (
    <div className="table-scroll">
      <table className="property-table">
        <thead><tr><th>Property</th><th>Location</th><th>Area</th><th>Estimated value</th><th>Annual rent</th><th>Occupancy</th><th>Ownership</th><th><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>{properties.map((property) => (
          <tr key={property.property_id}>
            <td><strong>{property.property_id}</strong><small>{property.property_type} · {property.sub_type}</small></td>
            <td>{property.location || "Data not available"}</td>
            <td>{property.area_sqft == null ? "Data not available" : `${Number(property.area_sqft).toLocaleString("en-IN")} sq ft`}</td>
            <td>{formatMoney(property.current_estimated_value_inr)}</td>
            <td>{formatMoney(property.annual_rent_inr)}</td>
            <td><StatusBadge tone={property.occupancy_status === "Occupied" ? "positive" : "neutral"}>{property.occupancy_status || "Data not available"}</StatusBadge></td>
            <td>{property.ownership_percent == null ? "Data not available" : `${property.ownership_percent}%`}</td>
            <td><button className="table-action" onClick={() => onEdit(property)} aria-label={`Edit ${property.property_id}`}>Edit</button></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function App() {
  const [view, setView] = useState("dashboard");
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
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
  const [portfolio, setPortfolio] = useState(null);
  const [rent, setRent] = useState(null);
  const [locations, setLocations] = useState([]);
  const [properties, setProperties] = useState([]);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [portfolioError, setPortfolioError] = useState("");
  const [propertiesLoading, setPropertiesLoading] = useState(false);
  const [propertiesError, setPropertiesError] = useState("");
  const [propertyEditor, setPropertyEditor] = useState(undefined);
  const [propertySaving, setPropertySaving] = useState(false);
  const [propertyFormError, setPropertyFormError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api("/admin/users")
      .then(({ users: rows }) => {
        if (cancelled) return;
        setUsers(rows);
        if (rows.length) setUserId((current) => current || rows[0].user_id);
      })
      .catch((requestError) => { if (!cancelled) setError(requestError.message); })
      .finally(() => { if (!cancelled) setUsersLoading(false); });
    return () => { cancelled = true; };
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
          { role: "assistant", text: row.assistant_response, hypothetical: row.assistant_response.startsWith("Hypothetical scenario only:") },
        ]);
        setMessages(transcript);
        setError("");
      })
      .catch((requestError) => setError(requestError.message));
  }, [userId]);

  useEffect(() => {
    if (!userId.trim() || !["dashboard", "properties"].includes(view)) return;
    let cancelled = false;
    const encodedUserId = encodeURIComponent(userId.trim());
    if (view === "dashboard") {
      setPortfolioLoading(true);
      setPortfolioError("");
      setPortfolio(null);
      setRent(null);
      setLocations([]);
      setProperties([]);
      Promise.all([
        api(`/users/${encodedUserId}/portfolio/summary`),
        api(`/users/${encodedUserId}/portfolio/rent`),
        api(`/users/${encodedUserId}/portfolio/by-location`),
        api(`/users/${encodedUserId}/properties`),
      ]).then(([summary, rentResult, locationResult, propertyResult]) => {
        if (cancelled) return;
        setPortfolio(summary);
        setRent(rentResult);
        setLocations(locationResult.locations || []);
        setProperties(propertyResult.properties || []);
      }).catch((requestError) => {
        if (!cancelled) setPortfolioError(requestError.message);
      }).finally(() => {
        if (!cancelled) setPortfolioLoading(false);
      });
    } else {
      setPropertiesLoading(true);
      setPropertiesError("");
      setProperties([]);
      api(`/users/${encodedUserId}/properties`)
        .then(({ properties: rows }) => { if (!cancelled) setProperties(rows || []); })
        .catch((requestError) => { if (!cancelled) setPropertiesError(requestError.message); })
        .finally(() => { if (!cancelled) setPropertiesLoading(false); });
    }
    return () => { cancelled = true; };
  }, [view, userId]);

  useEffect(() => {
    if (view !== "admin") return;
    let cancelled = false;
    setAdminLoading(true);
    setAdminError("");
    Promise.all([api("/admin/conversations"), api("/admin/tool-activity")])
      .then(([conversationResult, activityResult]) => {
        if (cancelled) return;
        setConversations(conversationResult.conversations);
        setActivity(activityResult.activity);
      })
      .catch((requestError) => { if (!cancelled) setAdminError(requestError.message); })
      .finally(() => { if (!cancelled) setAdminLoading(false); });
    return () => { cancelled = true; };
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
      setMessages((current) => [...current, {
        role: "assistant",
        text: result.response,
        hypothetical: result.tool_name === "hypothetical_value_change" || result.response.startsWith("Hypothetical scenario only:"),
        actualData: Boolean(result.tool_name && result.tool_name !== "hypothetical_value_change"),
      }]);
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

  async function saveProperty(event, form) {
    event.preventDefault();
    if (!userId.trim()) return;
    setPropertySaving(true);
    setPropertyFormError("");
    const numericFields = ["area_sqft", "current_estimated_value_inr", "purchase_price_inr", "annual_rent_inr", "ownership_percent"];
    const payload = { ...form };
    numericFields.forEach((field) => {
      if (payload[field] === "") delete payload[field];
      else payload[field] = Number(payload[field]);
    });
    try {
      const updateFields = ["location", "area_sqft", "current_estimated_value_inr", "purchase_price_inr", "annual_rent_inr", "occupancy_status", "tenant_status", "ownership_percent", "status"];
      const saved = propertyEditor
        ? await api(`/users/${encodeURIComponent(userId.trim())}/properties/${encodeURIComponent(propertyEditor.property_id)}`, {
          method: "PUT",
          body: JSON.stringify(Object.fromEntries(updateFields
            .filter((field) => payload[field] !== undefined && payload[field] !== "")
            .map((field) => [field, payload[field]]))),
        })
        : await api("/properties", {
          method: "POST",
          body: JSON.stringify({ ...payload, user_id: userId.trim() }),
        });
      setProperties((current) => propertyEditor
        ? current.map((row) => row.property_id === saved.property_id ? saved : row)
        : [...current, saved]);
      setPropertyEditor(undefined);
    } catch (requestError) {
      setPropertyFormError(requestError.message);
    } finally {
      setPropertySaving(false);
    }
  }

  const occupancy = properties.reduce((counts, property) => {
    const key = property.occupancy_status?.toLowerCase();
    if (key === "occupied") counts.occupied += 1;
    if (key === "vacant") counts.vacant += 1;
    return counts;
  }, { occupied: 0, vacant: 0 });
  const currentUser = users.find((user) => user.user_id === userId);
  const pageTitle = NAV_ITEMS.find((item) => item.id === view)?.label || "Dashboard";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#dashboard" onClick={() => setView("dashboard")}>
          <span className="brand-mark" aria-hidden="true">P</span>
          <span><strong>Portfolio</strong><small>REAL ESTATE ANALYST</small></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} onClick={() => setView(item.id)} aria-current={view === item.id ? "page" : undefined}>
              <span aria-hidden="true">{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>
        <OwnerPicker users={users} userId={userId} usersLoading={usersLoading} onChange={setUserId} includeManualInput />
        <div className="sidebar-footer"><span className="connection-dot" /> Connected to portfolio records</div>
      </aside>

      <main className="main-area">
        <header className="page-header">
          <div className="mobile-brand"><span className="brand-mark" aria-hidden="true">P</span><strong>Portfolio Analyst</strong></div>
          <div className="page-context"><div className="section-kicker">REAL ESTATE PORTFOLIO ANALYST</div><h1>{pageTitle}</h1></div>
          <div className="header-owner"><span className="owner-avatar">{currentUser?.name?.slice(0, 1) || "–"}</span><span><strong>{currentUser?.name || "Portfolio owner"}</strong><small>{userId || "No owner selected"}</small></span></div>
          <OwnerPicker users={users} userId={userId} usersLoading={usersLoading} onChange={setUserId} mobile />
          <nav className="mobile-nav" aria-label="Main navigation">
            {NAV_ITEMS.map((item) => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)} aria-label={item.label} aria-current={view === item.id ? "page" : undefined}><span aria-hidden="true">{item.icon}</span><small>{item.label}</small></button>)}
          </nav>
        </header>

        {!userId.trim() && <div className="page-notice" role="status">Choose a portfolio owner to view their records and ask questions.</div>}
        {error && view !== "chat" && <div className="page-notice error-notice" role="alert">{error}</div>}

        {view === "dashboard" && (
          <section className="content-page dashboard-page" aria-label="Portfolio dashboard">
            <div className="content-heading"><div><div className="section-kicker">PORTFOLIO OVERVIEW</div><h2>{currentUser ? `${currentUser.name}'s portfolio` : "Portfolio overview"}</h2></div><button className="primary-button" onClick={() => setView("chat")} disabled={!userId}><span aria-hidden="true">✳</span> Ask the analyst</button></div>
            {portfolioError && <div className="inline-error" role="alert">{portfolioError}</div>}
            {!userId ? <EmptyState title="Select an owner">Portfolio metrics are tied to the selected database user.</EmptyState> : portfolioLoading ? <LoadingState label="Loading portfolio overview" /> : (
              <>
                <div className="kpi-grid">
                  <KpiCard label="Total estimated value" value={formatMoney(portfolio?.total_estimated_value_inr)} note="Current portfolio records" icon="₹" />
                  <KpiCard label="Annual rental income" value={formatMoney(rent?.total_annual_rent_inr)} note="Across listed properties" icon="↗" />
                  <KpiCard label="Properties" value={portfolio?.property_count ?? "Data not available"} note="In this portfolio" icon="⌂" />
                  <KpiCard label="Occupancy" value={properties.length ? `${occupancy.occupied} occupied · ${occupancy.vacant} vacant` : "Data not available"} note="Based on property status" icon="◉" />
                </div>
                <div className="dashboard-grid">
                  <section className="surface-panel distribution-panel">
                    <div className="panel-heading"><div><div className="section-kicker">WHERE IT'S HELD</div><h3>Value by location</h3></div><span className="data-source">Actual data</span></div>
                    {locations.length ? <div className="location-list">{locations.map((item) => {
                      const totalValue = Number(portfolio?.total_estimated_value_inr || 0);
                      const share = totalValue > 0 ? (Number(item.total_value_inr || 0) / totalValue) * 100 : 0;
                      return <div className="location-row" key={item.location}><div className="location-copy"><strong>{item.location}</strong><span>{item.property_count} {item.property_count === 1 ? "property" : "properties"}</span><b>{formatMoney(item.total_value_inr)}</b></div><div className="value-track" aria-label={`${Math.round(share)} percent of portfolio`}><span style={{ width: `${Math.min(share, 100)}%` }} /></div></div>;
                    })}</div> : <EmptyState title="Location data not available" />}
                  </section>
                  <section className="surface-panel snapshot-panel">
                    <div className="panel-heading"><div><div className="section-kicker">PROPERTY MIX</div><h3>Portfolio snapshot</h3></div><span className="data-source">Actual data</span></div>
                    {!properties.length ? <EmptyState title="No property records" /> : <div className="snapshot-list">{properties.slice(0, 5).map((property) => <div className="snapshot-row" key={property.property_id}><span className="snapshot-icon" aria-hidden="true">⌂</span><span><strong>{property.property_id} · {property.property_type}</strong><small>{property.location}</small></span><b>{formatMoney(property.current_estimated_value_inr)}</b></div>)}</div>}
                    <button className="text-button" onClick={() => setView("properties")}>View all properties <span aria-hidden="true">→</span></button>
                  </section>
                </div>
                <div className="actual-note"><span aria-hidden="true">i</span> Portfolio figures are database-backed. Scenario analysis in chat is clearly labeled and does not alter recorded values.</div>
              </>
            )}
          </section>
        )}

        {view === "chat" && (
          <section className="content-page analyst-page" aria-label="Portfolio conversation">
            <div className="analyst-layout">
              <section className="chat-panel">
                <div className="chat-heading"><div><div className="section-kicker">PORTFOLIO DESK</div><h2>Ask your analyst</h2><p>Portfolio questions, property details, and scenario analysis.</p></div>{userId && <StatusBadge tone="positive">{userId}</StatusBadge>}</div>
                <div className="transcript" aria-live="polite" aria-relevant="additions text">
                  {messages.length === 0 && <div className="empty-state"><div className="empty-rule" /><p className="empty-overline">YOUR PORTFOLIO, IN CONTEXT</p><h3>What would you like to know?</h3><p>Start with a portfolio question or explore a property-specific scenario.</p><div className="prompt-grid">
                    {[
                      "What is my total portfolio value?",
                      "Which property has the highest current estimated value?",
                      "What is my total annual rental income?",
                      "Tell me about property P014.",
                      "What would P014 be worth if its value increased by 10%?",
                    ].map((prompt) => <button key={prompt} onClick={() => setDraft(prompt)} disabled={!userId}>{prompt}<span aria-hidden="true">↗</span></button>)}
                  </div></div>}
                  {messages.map((message, index) => <article className={`message ${message.role}`} key={`${index}-${message.role}`}>
                    <div className="message-label">{message.role === "user" ? userId || "YOU" : <>{message.hypothetical ? <StatusBadge tone="scenario">Hypothetical scenario</StatusBadge> : message.actualData ? <StatusBadge tone="positive">Actual data</StatusBadge> : "ANALYST"}</>}</div>
                    <p>{message.text}</p>
                  </article>)}
                  {loading && <LoadingState label="Analyzing portfolio" />}
                  {!messages.length && error && <div className="inline-error" role="alert">{error}</div>}
                </div>
                {messages.length > 0 && error && <div className="inline-error" role="alert">{error}</div>}
                <form className="composer" onSubmit={sendMessage}>
                  <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(event); }
                  }} placeholder={userId ? "Ask about this portfolio..." : "Select a portfolio owner first"} aria-label="Message the analyst" disabled={!userId || loading} rows="1" />
                  <button type="submit" aria-label="Send message" disabled={!draft.trim() || !userId || loading}><span>Send</span><b aria-hidden="true">↗</b></button>
                </form>
                <div className="composer-footnote"><span className="footnote-dot" /> Actual database facts stay separate from hypothetical scenarios.</div>
              </section>
              <aside className="analyst-aside"><div className="section-kicker">IN THIS SESSION</div><h3>{currentUser?.name || "Portfolio owner"}</h3><p>{userId ? `Portfolio ID ${userId}` : "Select an owner to load conversation history."}</p><div className="aside-divider" /><div className="aside-stat"><span>Messages in history</span><strong>{messages.filter((item) => item.role === "user").length}</strong></div><div className="aside-stat"><span>Record type</span><strong>Portfolio data</strong></div><button className="text-button" onClick={() => { setMessages([]); setError(""); }}>Clear view <span aria-hidden="true">↗</span></button><p className="aside-caption">Clearing the view does not delete saved conversation history.</p></aside>
            </div>
          </section>
        )}

        {view === "properties" && (
          <section className="content-page properties-page" aria-label="Properties">
            <div className="content-heading"><div><div className="section-kicker">DATABASE RECORDS</div><h2>Properties</h2><p>Property details associated with the selected portfolio.</p></div><button className="primary-button" onClick={() => { setPropertyFormError(""); setPropertyEditor(null); }} disabled={!userId}><span aria-hidden="true">＋</span> Add property</button></div>
            {propertiesError && <div className="inline-error" role="alert">{propertiesError}</div>}
            <section className="surface-panel property-panel"><div className="panel-heading"><div><h3>Property register</h3><p>{propertiesLoading ? "Refreshing records..." : `${properties.length} ${properties.length === 1 ? "record" : "records"}`}</p></div><span className="data-source">Actual data</span></div>
              {!userId ? <EmptyState title="Select a portfolio owner">Property records are scoped to the selected owner.</EmptyState> : propertiesLoading ? <LoadingState label="Loading property records" /> : <PropertyTable properties={properties} onEdit={(property) => { setPropertyFormError(""); setPropertyEditor(property); }} />}
            </section>
          </section>
        )}

        {view === "admin" && (
          <section className="content-page admin-page">
            <div className="content-heading"><div><div className="section-kicker">WORKSPACE MONITORING</div><h2>Operations</h2><p>Review conversations, attention flags, and tool activity.</p></div><span className="updated-tag">{adminLoading ? "Refreshing..." : `${users.length} users · ${conversations.length} conversations`}</span></div>
            {adminError && <div className="inline-error" role="alert">{adminError}</div>}
            {adminLoading ? <LoadingState label="Loading operations" /> : <div className="admin-grid">
              <section className="surface-panel users-section"><div className="panel-heading"><div><div className="section-kicker">ACCESS</div><h3>Users</h3></div><span className="count-badge">{users.length}</span></div><div className="user-list">{users.map((user) => <button className="user-row" key={user.user_id} onClick={() => { setUserId(user.user_id); setView("chat"); }}><span className="avatar">{user.name?.slice(0, 1) || "U"}</span><span><strong>{user.name}</strong><small>{user.city || "Location not set"}</small></span><code>{user.user_id}</code></button>)}{!users.length && <EmptyState title="No users available" />}</div></section>
              <section className="surface-panel conversations-section"><div className="panel-heading"><div><div className="section-kicker">REVIEW QUEUE</div><h3>Conversations</h3></div><span className="count-badge flagged-count">{conversations.filter((row) => row.flagged_for_attention).length} flagged</span></div><div className="conversation-list">{conversations.map((conversation) => <button className={`conversation-row ${conversation.flagged_for_attention ? "flagged" : ""} ${selectedConversation?.conversation_id === conversation.conversation_id ? "selected" : ""}`} key={conversation.conversation_id} onClick={() => openConversation(conversation.conversation_id)}><span className={`flag-marker ${conversation.flagged_for_attention ? "on" : ""}`} aria-label={conversation.flagged_for_attention ? "Flagged for attention" : "Not flagged"} /><span className="conversation-copy"><strong>{conversation.user_message}</strong><small>{conversation.user_id} · {conversation.created_at || "Time unavailable"}</small></span><span className="row-arrow" aria-hidden="true">↗</span></button>)}{!conversations.length && <EmptyState title="No conversations recorded" />}</div></section>
              <section className="surface-panel detail-section"><div className="panel-heading"><div><div className="section-kicker">TRANSCRIPT</div><h3>Conversation detail</h3></div></div>{selectedConversation ? <div className="detail-content"><div className="detail-meta"><span>{selectedConversation.user_id}</span><span>{selectedConversation.created_at || "Time unavailable"}</span></div>{selectedConversation.flagged_for_attention && <StatusBadge tone="attention">Flagged for attention</StatusBadge>}<div className="detail-message"><small>USER</small><p>{selectedConversation.user_message}</p></div><div className="detail-message assistant-detail"><small>ANALYST</small>{selectedConversation.assistant_response?.startsWith("Hypothetical scenario only:") && <StatusBadge tone="scenario">Hypothetical scenario</StatusBadge>}<p>{selectedConversation.assistant_response}</p></div><button className="secondary-button flag-button" onClick={() => toggleFlag(selectedConversation)}>{selectedConversation.flagged_for_attention ? "Remove attention flag" : "Flag for attention"}</button></div> : <EmptyState title="No conversation selected">Select an exchange to inspect its details.</EmptyState>}</section>
              <section className="surface-panel activity-section"><div className="panel-heading"><div><div className="section-kicker">EXECUTION LOG</div><h3>Tool activity</h3></div><span className="data-source">Recent</span></div><div className="activity-list">{activity.map((entry) => <div className="activity-row" key={entry.activity_id}><StatusBadge tone={entry.succeeded ? "positive" : "danger"}>{entry.succeeded ? "Success" : "Failed"}</StatusBadge><span><strong>{entry.tool_name}</strong><small>{entry.user_id} · {entry.created_at || "Time unavailable"}</small></span></div>)}{!activity.length && <EmptyState title="No tool activity recorded" />}</div></section>
            </div>}
          </section>
        )}
      </main>
      {propertyEditor !== undefined && <PropertyForm property={propertyEditor} busy={propertySaving} error={propertyFormError} onClose={() => setPropertyEditor(undefined)} onSubmit={saveProperty} />}
    </div>
  );
}

export default App;