import { type ReactNode, useEffect, useMemo, useState } from "react";
import logoUrl from "./assets/logo.png";

type ServiceState = "LIVE" | "DOWN";

type SentryEvent = {
  id: number;
  summary: string;
  route: string;
  age: string;
  status: number;
  level: string;
  fullError: string;
};

type RecommendedChange = {
  id: number;
  incident_id?: number;
  title?: string;
  summary: string;
  detail?: string;
  justification?: string;
  code?: string;
  code_patch?: string;
  validation_status?: string;
  validation_summary?: string;
  pr_creation_status?: string;
  pr_creation_error?: string | null;
  pr_url?: string | null;
  pr_number?: number | null;
  pr_branch?: string | null;
};

const sentryEvents: SentryEvent[] = [
  {
    id: 1,
    summary: "Failed login check",
    route: "GET /me",
    age: "2 min ago",
    status: 401,
    level: "warning",
    fullError:
      "Bogus backend request observed. Auth probe reached GET /me without valid credentials and returned 401.",
  },
  {
    id: 2,
    summary: "Unknown route requested",
    route: "GET /does-not-exist",
    age: "8 min ago",
    status: 404,
    level: "warning",
    fullError:
      "A client requested an unregistered route. The request matched no FastAPI handler and returned 404.",
  },
  {
    id: 3,
    summary: "Malformed todo payload",
    route: "POST /todos",
    age: "13 min ago",
    status: 422,
    level: "error",
    fullError:
      'Request body did not match the TodoCreate schema. Required field "title" was absent from the JSON payload.',
  },
  {
    id: 4,
    summary: "Chat provider crash",
    route: "POST /chat",
    age: "21 min ago",
    status: 500,
    level: "critical",
    fullError:
      "Gemini client raised an upstream exception. Check API key, timeout behavior, and fallback response path.",
  },
];

const recommendedChanges: RecommendedChange[] = [
  {
    id: 1,
    summary: "Group expected auth failures",
    detail:
      "Reduce alert noise from normal unauthenticated checks while keeping scanner activity visible in Sentry.",
    code: `- sentry_sdk.capture_message("Bogus backend request observed")
+ sentry_sdk.capture_message(
+   "Expected unauthenticated probe observed",
+   level="info",
+ )`,
  },
  {
    id: 2,
    summary: "Add source fingerprinting",
    detail:
      "Make repeated bogus requests easier to sort by route and status without creating hundreds of separate issues.",
    code: `+ with sentry_sdk.configure_scope() as scope:
+   scope.fingerprint = [
+     "bogus-backend-request",
+     request.method,
+     request.url.path,
+     str(response.status_code),
+   ]`,
  },
  {
    id: 3,
    summary: "Forward critical events to intake app",
    detail:
      "Send 500-level events directly to the second app while keeping lower-severity warnings in Sentry.",
  },
];

const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("DOWN");
  const [healthPercentage, setHealthPercentage] = useState(100);
  const [openEvents, setOpenEvents] = useState<number[]>([3, 4]);
  const [openChanges, setOpenChanges] = useState<number[]>([1]);
  const [changes, setChanges] = useState<RecommendedChange[]>(recommendedChanges);
  const [prPending, setPrPending] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${apiBaseUrl}/api/recommendations/`)
      .then((response) => {
        if (!response.ok) throw new Error("Recommendations are unavailable");
        return response.json() as Promise<RecommendedChange[]>;
      })
      .then(setChanges)
      .catch(() => {
        // Keep the existing demo recommendations when the backend is offline.
      });
  }, []);

  const createPr = async (id: number) => {
    setPrPending(id);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/recommendations/${id}/pull-request`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("Pull request creation failed");
      const updated = (await response.json()) as RecommendedChange;
      setChanges((current) =>
        current.map((change) => (change.id === id ? updated : change)),
      );
    } finally {
      setPrPending(null);
    }
  };

  const healthTone = useMemo(() => {
    if (healthPercentage >= 80) {
      return {
        text: "text-[#7cf083]",
        border: "border-[#78e86f]",
        bar: "bg-[#78e86f]",
        label: "Healthy",
      };
    }

    if (healthPercentage >= 70) {
      return {
        text: "text-[#f2d84b]",
        border: "border-[#e8ca38]",
        bar: "bg-[#e8ca38]",
        label: "Watch",
      };
    }

    return {
      text: "text-[#ff6f82]",
      border: "border-[#ef6478]",
      bar: "bg-[#ef6478]",
      label: "Risk",
    };
  }, [healthPercentage]);

  const toggleEvent = (id: number) => {
    setOpenEvents((open) =>
      open.includes(id)
        ? open.filter((eventId) => eventId !== id)
        : [...open, id],
    );
  };

  const toggleChange = (id: number) => {
    setOpenChanges((open) =>
      open.includes(id)
        ? open.filter((changeId) => changeId !== id)
        : [...open, id],
    );
  };

  return (
    <main className="min-h-screen bg-[#0d0b2c] text-[#f7f4ff]">
      <div className="mx-auto flex min-h-screen w-full max-w-[1920px] flex-col border-x border-[#2d2a65] bg-[#11103a] px-3 py-3 sm:px-5 lg:px-8">
        <header className="flex flex-wrap items-start justify-between gap-5 pb-7">
          <div className="flex min-w-0 items-start gap-5">
            <div className="grid h-[4.25rem] w-[4.25rem] shrink-0 place-items-center rounded-[1.1rem] border border-[#4b4a86] bg-[#29285c] shadow-[inset_0_0_0_6px_rgba(255,255,255,0.04)]">
              <img
                src={logoUrl}
                alt="Logo placeholder"
                className="h-11 w-11 rounded-md object-contain"
              />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-black uppercase tracking-[0.18em] text-[#b7b3d7]">
                Security Signal Board
              </p>
              <h1 className="mt-1 text-5xl font-black leading-none tracking-[-0.02em] text-[#fbf8ff] sm:text-6xl lg:text-7xl">
                Backend Observability
              </h1>
            </div>
          </div>

          <div className="rounded-bl-[1.4rem] rounded-br-lg rounded-tl-lg rounded-tr-[1.4rem] border border-[#45437d] bg-[#29285e] px-5 py-4 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
            <p className="bg-[#7f92c8] px-1 text-xl leading-none text-[#d9def8]">
              Sentry intake
            </p>
            <p className="mt-2 text-2xl font-black text-white">local</p>
          </div>
        </header>

        <section className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[470px_minmax(480px,1fr)_minmax(500px,1fr)]">
          <Panel
            title="Overall Health"
            badge={serviceState === "LIVE" ? "Live" : "Down"}
            badgeTone={serviceState === "LIVE" ? "live" : "down"}
          >
            <div className="rounded-[1.65rem] border border-[#46447b] bg-[#373568] px-6 py-16 text-center">
              <p
                className={`text-7xl font-black leading-none tracking-[-0.04em] sm:text-8xl ${
                  serviceState === "LIVE" ? "text-[#74f082]" : "text-[#ff6f82]"
                }`}
              >
                {serviceState}
              </p>
            </div>

            <div className="mt-5 space-y-4">
              <label className="block">
                <span className="text-sm font-black text-[#cbc7e6]">
                  Service state
                </span>
                <select
                  value={serviceState}
                  onChange={(event) =>
                    setServiceState(event.target.value as ServiceState)
                  }
                  className="mt-2 h-12 w-full rounded-lg border border-[#2b2a61] bg-[#171740] px-4 text-base font-black text-white outline-none focus:border-[#6b73d6]"
                >
                  <option>LIVE</option>
                  <option>DOWN</option>
                </select>
              </label>

              <label className="block">
                <span className="text-sm font-black text-[#cbc7e6]">
                  Health percentage
                </span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={healthPercentage}
                  onChange={(event) =>
                    setHealthPercentage(
                      Math.min(100, Math.max(0, Number(event.target.value))),
                    )
                  }
                  className="mt-2 h-12 w-full rounded-lg border border-[#2b2a61] bg-[#171740] px-4 text-base font-black text-white outline-none focus:border-[#6b73d6]"
                />
              </label>

              <div className="rounded-xl bg-[#181742] px-5 py-5">
                <div className="flex items-end justify-between gap-4">
                  <p
                    className={`text-6xl font-black leading-none ${healthTone.text}`}
                  >
                    {healthPercentage}%
                  </p>
                  <p className="pb-2 text-lg font-black text-[#f0ecff]">
                    {healthTone.label}
                  </p>
                </div>
                <div className="mt-5 h-2 rounded-full bg-[#2b2a5d]">
                  <div
                    className={`h-full rounded-full ${healthTone.bar}`}
                    style={{ width: `${healthPercentage}%` }}
                  />
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Events" badge={`${sentryEvents.length} observed`}>
            <p className="text-lg text-[#b7b3d2]">
              Precise Sentry events land here. Expand one to inspect the full
              error.
            </p>

            <div className="mt-12 max-h-[58vh] space-y-4 overflow-y-auto pr-1">
              {sentryEvents.map((event) => {
                const isOpen = openEvents.includes(event.id);

                return (
                  <ExpandableRow
                    key={event.id}
                    isOpen={isOpen}
                    onToggle={() => toggleEvent(event.id)}
                    accent={
                      event.status >= 500
                        ? "red"
                        : event.status >= 422
                          ? "pink"
                          : "yellow"
                    }
                    summary={event.summary}
                    meta={`${event.route} - ${event.age}`}
                    chip={event.status}
                  >
                    <p className="text-xl leading-7 text-[#d7d2ef]">
                      {event.fullError}
                    </p>
                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                      <Metric label="Level" value={event.level} />
                      <Metric label="Route" value={event.route} />
                      <Metric label="Status" value={String(event.status)} />
                    </div>
                  </ExpandableRow>
                );
              })}
            </div>
          </Panel>

          <Panel
            title="Recommended Changes"
            badge={`${changes.length} queued`}
          >
            <p className="text-lg text-[#b7b3d2]">
              AI-generated fixes can include exact code edits in the code box.
            </p>

            <div className="mt-12 max-h-[58vh] space-y-4 overflow-y-auto pr-1">
              {changes.map((change) => {
                const isOpen = openChanges.includes(change.id);

                return (
                  <ExpandableRow
                    key={change.id}
                    isOpen={isOpen}
                    onToggle={() => toggleChange(change.id)}
                    summary={change.title ?? change.summary}
                    meta={change.justification ?? change.detail ?? ""}
                  >
                    {change.code_patch || change.code ? (
                      <pre className="mt-2 max-h-72 overflow-auto rounded-xl border border-[#414078] bg-[#111034] p-4 text-sm leading-6 text-[#e7e2ff]">
                        <code>{change.code_patch ?? change.code}</code>
                      </pre>
                    ) : (
                      <div className="mt-2 rounded-xl border border-dashed border-[#504e86] bg-[#242456] p-5 text-[#aaa6ca]">
                        Code recommendation area
                      </div>
                    )}
                    {change.validation_status ? (
                      <div className="mt-4 rounded-xl border border-[#414078] bg-[#191944] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-black uppercase tracking-wide text-[#aaa6ca]">
                              Validation: {change.validation_status}
                            </p>
                            <p className="mt-1 text-sm text-[#d7d2ef]">
                              {change.validation_summary}
                            </p>
                          </div>
                          {change.pr_url ? (
                            <a
                              href={change.pr_url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-lg bg-[#78e86f] px-4 py-2 text-sm font-black text-[#102415] hover:bg-[#92f18b]"
                            >
                              Open PR #{change.pr_number}
                            </a>
                          ) : (
                            <button
                              type="button"
                              disabled={
                                change.validation_status !== "approved" ||
                                prPending === change.id
                              }
                              onClick={() => void createPr(change.id)}
                              className="rounded-lg bg-[#6b73d6] px-4 py-2 text-sm font-black text-white hover:bg-[#7e86e5] disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {prPending === change.id ? "Creating…" : "Create PR"}
                            </button>
                          )}
                        </div>
                        {change.pr_creation_status ? (
                          <p className="mt-3 text-xs font-bold uppercase tracking-wide text-[#9e9abd]">
                            PR status: {change.pr_creation_status}
                            {change.pr_branch ? ` · ${change.pr_branch}` : ""}
                          </p>
                        ) : null}
                        {change.pr_creation_error ? (
                          <p className="mt-2 text-sm text-[#ff9aab]">
                            {change.pr_creation_error}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                  </ExpandableRow>
                );
              })}
            </div>
          </Panel>
        </section>
      </div>
    </main>
  );
}

type PanelProps = {
  title: string;
  badge: string;
  badgeTone?: "live" | "down";
  children: ReactNode;
};

function Panel({ title, badge, badgeTone, children }: PanelProps) {
  return (
    <article className="min-h-[580px] rounded-xl border border-[#383671] bg-[#2a2a5c] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
      <div className="flex items-center justify-between gap-4 border-b border-[#464376] pb-5">
        <h2 className="text-3xl font-black tracking-[-0.03em] text-white">
          {title}
        </h2>
        <span
          className={`rounded-full border px-4 py-2 text-sm font-bold ${
            badgeTone === "live"
              ? "border-[#4e8d65] bg-[#345d4b] text-[#99f3a6]"
              : badgeTone === "down"
                ? "border-[#7d4b68] bg-[#42315f] text-[#f2a3b2]"
                : "border-[#4d4b78] bg-[#3a396b] text-[#cbc7e6]"
          }`}
        >
          {badge}
        </span>
      </div>
      <div className="pt-5">{children}</div>
    </article>
  );
}

type ExpandableRowProps = {
  isOpen: boolean;
  onToggle: () => void;
  summary: string;
  meta: string;
  chip?: string | number;
  accent?: "yellow" | "pink" | "red";
  children: ReactNode;
};

function ExpandableRow({
  isOpen,
  onToggle,
  summary,
  meta,
  chip,
  accent,
  children,
}: ExpandableRowProps) {
  const chipTone =
    accent === "red"
      ? "text-[#ff7585]"
      : accent === "pink"
        ? "text-[#ff7f98]"
        : "text-[#f7dc4d]";

  return (
    <div
      className={`rounded-lg border bg-[#191944] px-4 py-4 transition-colors ${
        isOpen ? "border-[#3154a9] bg-[#20255a]" : "border-[#313063]"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-lg font-black leading-6 text-white">{summary}</h3>
          <p className="mt-1 text-base font-semibold leading-5 text-[#b8b3d2]">
            {meta}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {chip ? (
            <span
              className={`rounded-full bg-[#393966] px-3 py-1 text-lg font-black ${chipTone}`}
            >
              {chip}
            </span>
          ) : null}
          <button
            type="button"
            onClick={onToggle}
            className="h-10 rounded-lg border border-[#4b4a82] bg-[#414073] px-4 text-sm font-black text-white hover:bg-[#52518b]"
          >
            {isOpen ? "Close" : "Open"}
          </button>
        </div>
      </div>

      {isOpen ? <div className="mt-5">{children}</div> : null}
    </div>
  );
}

type MetricProps = {
  label: string;
  value: string;
};

function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-lg bg-[#343365] px-4 py-3">
      <p className="text-xs font-black uppercase text-[#a6a1c5]">{label}</p>
      <p className="mt-1 text-xl text-[#ded9f5]">{value}</p>
    </div>
  );
}

export default App;
