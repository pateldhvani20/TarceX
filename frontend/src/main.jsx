import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  API_BASE_URL,
  API_HOST,
  ApiError,
  buildIngestPayload,
  getHealth,
  getStats,
  getTransactions,
  ingestTransaction,
} from "./api";
import "./styles.css";

const NAV_ITEMS = [
  "Overview",
  "Transactions",
  "Anomaly Detection",
  "Identity Resolution",
  "Temporal Replay",
  "Audit Trail",
  "System Health",
];

const initialForm = {
  event_id: `ui-${Date.now()}`,
  timestamp: new Date().toISOString(),
  source: "BankA",
  user_id: "user-ui",
  amount: "125.50",
  category: "retail",
  description: "Frontend demo transaction",
  merchant: "TraceX Demo Store",
  status: "completed",
  email: "demo@tracex.local",
  phone: "+1555010101",
};

function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDecisionLabel(decision) {
  if (!decision) {
    return "PENDING";
  }

  return String(decision).replace(/_/g, " ").trim().toUpperCase();
}

function decisionClassName(decision) {
  const value = String(decision || "pending")
    .toLowerCase()
    .replace(/\s+/g, "-");
  return value;
}

function normalizeDecision(transaction) {
  if (transaction.decision) {
    return transaction.decision;
  }

  if (transaction.decision_reason?.toLowerCase().includes("identity")) {
    return "updated";
  }

  if (transaction.decision_reason?.toLowerCase().includes("duplicate conflict")) {
    return "duplicate conflict";
  }

  if (transaction.decision_reason?.toLowerCase().includes("duplicate")) {
    return "duplicate";
  }

  return "pending";
}

function describeRequestError(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error?.message === "Failed to fetch" || error?.name === "TypeError") {
    return `Backend offline — unable to reach ${API_HOST}. Start FastAPI from the TarceX folder and try again.`;
  }

  return error?.message || "Unexpected request error";
}

function App() {
  const [activePage, setActivePage] = useState("Overview");
  const [stats, setStats] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState(initialForm);
  const [submitState, setSubmitState] = useState({
    loading: false,
    result: null,
    error: "",
  });

  async function checkHealth() {
    try {
      const healthData = await getHealth();
      setHealth(healthData);
      return true;
    } catch {
      setHealth(null);
      return false;
    }
  }

  async function loadLiveData(isInitial = false) {
    if (isInitial) {
      setLoading(true);
    }

    try {
      const online = await checkHealth();
      if (!online) {
        setError(`Backend Offline — ${API_HOST}`);
        return;
      }

      const [statsData, transactionData] = await Promise.all([
        getStats(),
        getTransactions(),
      ]);

      setStats(statsData);
      setTransactions(transactionData.transactions || []);
      setError("");
    } catch (requestError) {
      setError(describeRequestError(requestError));
      if (requestError instanceof ApiError && requestError.offline) {
        setHealth(null);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLiveData(true);

    // Health every 20s; full data refresh every 30s (avoid spamming).
    const healthId = window.setInterval(() => {
      checkHealth();
    }, 20000);
    const dataId = window.setInterval(() => {
      loadLiveData(false);
    }, 30000);

    return () => {
      window.clearInterval(healthId);
      window.clearInterval(dataId);
    };
  }, []);

  const newestFirst = useMemo(
    () =>
      [...transactions].sort(
        (a, b) =>
          new Date(b.processed_at || b.timestamp) -
          new Date(a.processed_at || a.timestamp)
      ),
    [transactions]
  );

  const chronological = useMemo(
    () =>
      [...transactions].sort(
        (a, b) =>
          new Date(a.timestamp || a.processed_at) -
          new Date(b.timestamp || b.processed_at)
      ),
    [transactions]
  );

  const derived = useMemo(() => {
    const totalAmount = transactions.reduce(
      (sum, item) => sum + Number(item.amount || 0),
      0
    );

    const late = transactions.filter((item) => item.is_late).length;
    const identity = transactions.filter((item) =>
      item.decision_reason?.toLowerCase().includes("identity")
    ).length;

    return {
      totalAmount,
      late,
      identity,
      averageAmount: transactions.length ? totalAmount / transactions.length : 0,
    };
  }, [transactions]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitState({ loading: true, result: null, error: "" });

    try {
      const payload = buildIngestPayload(form);
      const result = await ingestTransaction(payload);

      setSubmitState({ loading: false, result, error: "" });
      setForm({
        ...form,
        event_id: `ui-${Date.now()}`,
        timestamp: new Date().toISOString(),
      });
      await loadLiveData(false);
    } catch (submitError) {
      setSubmitState({
        loading: false,
        result: null,
        error: describeRequestError(submitError),
      });
      if (submitError instanceof ApiError && submitError.offline) {
        setHealth(null);
      }
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">TX</div>
          <div>
            <strong>TraceX</strong>
            <span>Transaction Intelligence</span>
          </div>
        </div>

        <nav>
          {NAV_ITEMS.map((item) => (
            <button
              className={activePage === item ? "nav-item active" : "nav-item"}
              key={item}
              onClick={() => setActivePage(item)}
              type="button"
            >
              <span className="nav-dot" />
              {item}
            </button>
          ))}
        </nav>

        <div className="connection-card">
          <span
            className={health ? "status-light online" : "status-light offline"}
          />
          <div>
            <strong>{health ? "Backend Online" : "Backend Offline"}</strong>
            <span>{API_HOST}</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">TraceX Monitoring Console</p>
            <h1>{activePage}</h1>
          </div>
          <button
            className="primary-action"
            onClick={() => setActivePage("Anomaly Detection")}
            type="button"
          >
            Submit Transaction
          </button>
        </header>

        {error && <ErrorBanner message={error} />}
        {loading ? (
          <LoadingState />
        ) : (
          <Page
            activePage={activePage}
            stats={stats}
            transactions={newestFirst}
            chronological={chronological}
            derived={derived}
            form={form}
            setForm={setForm}
            submitState={submitState}
            handleSubmit={handleSubmit}
            health={health}
          />
        )}
      </main>
    </div>
  );
}

function Page(props) {
  if (props.activePage === "Transactions") {
    return <TransactionsPage transactions={props.transactions} />;
  }

  if (props.activePage === "Anomaly Detection") {
    return <IngestPage {...props} />;
  }

  if (props.activePage === "Identity Resolution") {
    return <IdentityPage {...props} />;
  }

  if (props.activePage === "Temporal Replay") {
    return <ReplayPage transactions={props.chronological} />;
  }

  if (props.activePage === "Audit Trail") {
    return <AuditPage transactions={props.transactions} />;
  }

  if (props.activePage === "System Health") {
    return <HealthPage {...props} />;
  }

  return <OverviewPage {...props} />;
}

function OverviewPage({ stats, transactions, derived }) {
  return (
    <>
      <section className="kpi-grid">
        <KpiCard label="Total Events" value={stats?.total_events ?? 0} tone="pink" />
        <KpiCard
          label="Decisions"
          value={stats?.total_decisions ?? 0}
          tone="purple"
        />
        <KpiCard label="Anomalies" value={stats?.anomalous ?? 0} tone="alert" />
        <KpiCard
          label="Identity Conflicts"
          value={stats?.identity_conflict ?? 0}
          tone="lavender"
        />
      </section>

      <section className="dashboard-grid">
        <Panel title="Transaction Activity" subtitle="Real backend events">
          <ActivityChart transactions={transactions} />
        </Panel>
        <Panel title="Decision Distribution" subtitle="From /stats">
          <DecisionChart stats={stats} />
        </Panel>
      </section>

      <section className="dashboard-grid wide-left">
        <Panel title="Live Decision Feed" subtitle="Refreshes every 30s">
          <DecisionFeed transactions={transactions.slice(0, 7)} />
        </Panel>
        <Panel title="Signal Snapshot" subtitle="Derived from real records">
          <div className="signal-list">
            <MetricRow label="Observed volume" value={formatCurrency(derived.totalAmount)} />
            <MetricRow label="Average ticket" value={formatCurrency(derived.averageAmount)} />
            <MetricRow label="Late arrivals" value={derived.late} />
            <MetricRow label="Resolved identities" value={derived.identity} />
          </div>
        </Panel>
      </section>
    </>
  );
}

function TransactionsPage({ transactions }) {
  return (
    <Panel title="Transactions" subtitle="Joined /transactions event and decision records">
      <TransactionTable transactions={transactions} />
    </Panel>
  );
}

function IngestPage({
  form,
  setForm,
  submitState,
  handleSubmit,
  transactions,
}) {
  function updateField(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  return (
    <section className="dashboard-grid wide-left">
      <Panel title="Transaction Submission" subtitle="POST /ingest">
        <form className="ingest-form" onSubmit={handleSubmit}>
          {[
            ["event_id", "Event ID"],
            ["timestamp", "Timestamp"],
            ["source", "Source"],
            ["user_id", "User ID"],
            ["amount", "Amount"],
            ["category", "Category"],
            ["merchant", "Merchant"],
            ["status", "Status"],
            ["email", "Email"],
            ["phone", "Phone"],
          ].map(([name, label]) => (
            <label key={name}>
              <span>{label}</span>
              <input
                name={name}
                onChange={(event) => updateField(name, event.target.value)}
                required={["event_id", "timestamp", "source", "user_id", "amount"].includes(name)}
                step={name === "amount" ? "0.01" : undefined}
                type={name === "amount" ? "number" : "text"}
                value={form[name]}
              />
            </label>
          ))}
          <label className="full-field">
            <span>Description</span>
            <input
              name="description"
              onChange={(event) => updateField("description", event.target.value)}
              value={form.description}
            />
          </label>

          <button className="primary-action full-field" disabled={submitState.loading} type="submit">
            {submitState.loading ? "Submitting..." : "Run TraceX Decision"}
          </button>
        </form>
      </Panel>

      <Panel title="Decision Result" subtitle="Backend response">
        {submitState.error && <ErrorBanner message={submitState.error} />}
        {submitState.result ? (
          <div className="result-card">
            <div className="decision-hero">
              <DecisionBadge decision={submitState.result.decision} large />
            </div>
            <MetricRow label="Event ID" value={submitState.result.event_id} />
            <MetricRow label="Status" value={submitState.result.status} />
            <MetricRow label="Decision" value={formatDecisionLabel(submitState.result.decision)} />
            <MetricRow label="Reason" value={submitState.result.reason} />
          </div>
        ) : (
          <EmptyState text="Submit a transaction to see the real pipeline decision." />
        )}
        <DecisionFeed transactions={transactions.slice(0, 4)} />
      </Panel>
    </section>
  );
}

function IdentityPage({ transactions, stats }) {
  const identityRows = transactions.filter((item) =>
    item.decision_reason?.toLowerCase().includes("identity")
  );

  return (
    <section className="dashboard-grid wide-left">
      <Panel title="Signal Convergence Topology" subtitle="Identity signals from transaction records">
        <div className="topology">
          <div className="node primary">User</div>
          <div className="node">Email</div>
          <div className="node">Phone</div>
          <div className="node">Event</div>
          <div className="node alert">{stats?.identity_conflict ?? 0} conflicts</div>
        </div>
      </Panel>
      <Panel title="Identity Consolidation Matrix" subtitle="Real conflict decisions">
        {identityRows.length ? (
          <TransactionTable transactions={identityRows} compact />
        ) : (
          <EmptyState text="No identity conflicts are present in the current backend data." />
        )}
      </Panel>
    </section>
  );
}

function ReplayPage({ transactions }) {
  return (
    <Panel title="Temporal Replay" subtitle="Chronological view from /transactions">
      {transactions.length ? (
        <div className="timeline">
          {transactions.map((item, index) => (
            <article className="timeline-item" key={item.event_id}>
              <div className="timeline-marker">{index + 1}</div>
              <div className="timeline-body">
                <div className="timeline-top">
                  <strong>{item.event_id}</strong>
                  <DecisionBadge decision={normalizeDecision(item)} />
                </div>
                <p>
                  {formatDate(item.timestamp)} · {item.source} · {formatCurrency(item.amount)}
                </p>
                <span>{item.decision_reason || "No decision reason recorded."}</span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState text="No backend events available to replay yet." />
      )}
    </Panel>
  );
}

function AuditPage({ transactions }) {
  return (
    <Panel title="Audit Trail" subtitle="Decision reasons from persisted pipeline output">
      {transactions.length ? (
        <div className="feed">
          {transactions.map((item) => (
            <article className="feed-item" key={`audit-${item.event_id}`}>
              <div>
                <strong>{item.event_id}</strong>
                <span>
                  {formatDate(item.processed_at || item.timestamp)} ·{" "}
                  {item.decision_reason || "No audit reason"}
                </span>
              </div>
              <DecisionBadge decision={normalizeDecision(item)} />
            </article>
          ))}
        </div>
      ) : (
        <EmptyState text="No audit-ready decisions are available yet." />
      )}
    </Panel>
  );
}

function HealthPage({ health, stats, transactions }) {
  return (
    <section className="dashboard-grid">
      <Panel title="Backend Status" subtitle="/health">
        <div className="health-card">
          <span className={health ? "status-light online" : "status-light offline"} />
          <strong>{health ? "Backend Online" : "Backend Offline"}</strong>
          <p>{API_HOST}</p>
          <p>{health?.service || "TraceX service unreachable"}</p>
        </div>
      </Panel>
      <Panel title="Data Contracts" subtitle="Live endpoint checks">
        <div className="signal-list">
          <MetricRow label="/stats total_events" value={stats?.total_events ?? 0} />
          <MetricRow label="/transactions count" value={transactions.length} />
          <MetricRow label="/ingest" value="available" />
          <MetricRow label="/health" value={health ? "healthy" : "offline"} />
          <MetricRow label="API base" value={API_BASE_URL} />
        </div>
      </Panel>
    </section>
  );
}

function KpiCard({ label, value, tone }) {
  return (
    <article className={`kpi-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>Live backend value</small>
    </article>
  );
}

function Panel({ title, subtitle, children }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function ActivityChart({ transactions }) {
  const buckets = transactions.slice(0, 12).reverse();
  const max = Math.max(...buckets.map((item) => Number(item.amount || 0)), 1);

  if (!buckets.length) {
    return <EmptyState text="No backend transactions yet." />;
  }

  return (
    <div className="bar-chart">
      {buckets.map((item) => (
        <div className="bar-item" key={item.event_id}>
          <div
            className="bar"
            style={{ height: `${Math.max((Number(item.amount || 0) / max) * 100, 8)}%` }}
            title={`${item.event_id}: ${formatCurrency(item.amount)}`}
          />
          <span>{item.source}</span>
        </div>
      ))}
    </div>
  );
}

function DecisionChart({ stats }) {
  const normal = stats?.normal ?? 0;
  const anomalous = stats?.anomalous ?? 0;
  const duplicate = stats?.duplicate ?? 0;
  const updated = stats?.updated ?? 0;
  const total = Math.max(normal + anomalous + duplicate + updated, 1);
  const segments = [
    ["Normal", normal, "success"],
    ["Anomalous", anomalous, "alert"],
    ["Duplicate", duplicate, "lavender"],
    ["Updated", updated, "purple"],
  ];

  return (
    <div className="decision-chart">
      <div
        className="donut"
        style={{
          background: `conic-gradient(#ec4899 0 ${normal / total}turn, #a855f7 ${normal / total}turn ${(normal + anomalous) / total}turn, #f9a8d4 ${(normal + anomalous) / total}turn ${(normal + anomalous + duplicate) / total}turn, #7c3aed ${(normal + anomalous + duplicate) / total}turn 1turn)`,
        }}
      >
        <span>{stats?.total_decisions ?? 0}</span>
      </div>
      <div className="legend">
        {segments.map(([label, value, tone]) => (
          <MetricRow key={label} label={label} value={value} tone={tone} />
        ))}
      </div>
    </div>
  );
}

function DecisionFeed({ transactions }) {
  if (!transactions.length) {
    return <EmptyState text="No decision records available." />;
  }

  return (
    <div className="feed">
      {transactions.map((item) => (
        <article className="feed-item" key={item.event_id}>
          <div>
            <strong>{item.event_id}</strong>
            <span>{item.merchant || "unknown merchant"} - {formatCurrency(item.amount)}</span>
          </div>
          <DecisionBadge decision={normalizeDecision(item)} />
        </article>
      ))}
    </div>
  );
}

function TransactionTable({ transactions, compact = false }) {
  if (!transactions.length) {
    return <EmptyState text="No transactions returned by the backend." />;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Event</th>
            <th>User</th>
            <th>Source</th>
            <th>Amount</th>
            {!compact && <th>Merchant</th>}
            <th>Decision</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((item) => (
            <tr key={item.event_id}>
              <td>{item.event_id}</td>
              <td>{item.user_id}</td>
              <td>{item.source}</td>
              <td>{formatCurrency(item.amount)}</td>
              {!compact && <td>{item.merchant || "-"}</td>}
              <td><DecisionBadge decision={normalizeDecision(item)} /></td>
              <td>{formatDate(item.processed_at || item.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DecisionBadge({ decision, large = false }) {
  const className = `badge ${decisionClassName(decision)}${large ? " large" : ""}`;
  return <span className={className}>{formatDecisionLabel(decision)}</span>;
}

function MetricRow({ label, value, tone = "" }) {
  return (
    <div className={`metric-row ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="loading-state">
      <div className="loader" />
      <p>Connecting to TraceX backend...</p>
    </div>
  );
}

function ErrorBanner({ message }) {
  return <div className="error-banner">{message}</div>;
}

function EmptyState({ text }) {
  return <div className="empty-state">{text}</div>;
}

createRoot(document.getElementById("root")).render(<App />);
