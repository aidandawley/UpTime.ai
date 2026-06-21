import { useMemo, useState } from 'react'
import logo from './assets/logo.png'

type ServiceStatus = 'LIVE' | 'DOWN'

type EventItem = {
  id: string
  title: string
  code: number
  time: string
  severity: string
  route: string
  raw: string
}

type FixItem = {
  id: string
  title: string
  status: string
  summary: string
  justification: string
  code: string
}

const events: EventItem[] = [
  {
    id: 'evt-101',
    title: 'ZeroDivisionError',
    code: 500,
    time: '1 min ago',
    severity: 'error',
    route: 'GET /crash',
    raw: `ZeroDivisionError: division by zero
transaction: app.main.crash
route: GET /crash
handled: false
file: backend/app/main.py:110
line: return 1 / 0`,
  },
  {
    id: 'evt-102',
    title: 'Bogus backend request observed',
    code: 404,
    time: '8 min ago',
    severity: 'warning',
    route: 'GET /sentry-mega-error',
    raw: `Bogus backend request observed
event_type: bogus_backend_request
method: GET
route: /sentry-mega-error
status_code: 404
decision: likely client or scanner noise`,
  },
  {
    id: 'evt-103',
    title: 'Webhook recommendation state failed',
    code: 500,
    time: '18 min ago',
    severity: 'error',
    route: 'POST /api/sentry/webhook',
    raw: `ImpossibleWebhookStateError: Webhook event entered an impossible recommendation state
transaction: app.routes.sentry.sentry_webhook
route: POST /api/sentry/webhook
level: error
agent_handoff: failed_to_start`,
  },
]

const fixes: FixItem[] = [
  {
    id: 'fix-201',
    title: 'Guard crash route before division',
    status: 'ready',
    summary: 'Patch Agent recommends replacing the direct division with explicit validation.',
    justification:
      'The stack trace points directly to backend/app/main.py inside app.main.crash. A small guard keeps the endpoint from throwing an unhandled 500 while preserving a clear failure response for the caller.',
    code: `--- backend/app/main.py
+++ backend/app/main.py
@@
-    return 1 / 0
+    raise HTTPException(status_code=500, detail="Crash route triggered intentionally")`,
  },
  {
    id: 'fix-202',
    title: 'Ignore scanner-style 404 alerts',
    status: 'review',
    summary: 'Investigation Agent classified the bogus request as low-priority noise.',
    justification:
      'The event includes event_type=bogus_backend_request with a 404 status code. It should remain visible in history without spending GitHub/Patch/Validation cycles.',
    code: `decision:
  continue_pipeline: false
  reason: "Likely expected client or scanner noise."
  status_code: 404`,
  },
  {
    id: 'fix-203',
    title: 'Persist workflow trace outcome',
    status: 'queued',
    summary: 'Store the final validation summary for display in the recommended fixes panel.',
    justification:
      'Validation currently emits a clean result into the trace log. The frontend will need a stable DB/API source for title, justification, changed files, and code text.',
    code: `recommended_next_step:
  table: workflow_recommendation
  fields:
    - incident_id
    - title
    - justification
    - code_patch
    - validation_status`,
  },
]

function App() {
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>('LIVE')
  const [health, setHealth] = useState(92)
  const [openEvent, setOpenEvent] = useState(events[0].id)
  const [openFix, setOpenFix] = useState(fixes[0].id)

  const healthTone = useMemo(() => {
    if (health >= 80) {
      return {
        text: 'text-emerald-300',
        bar: 'bg-emerald-400',
        ring: 'border-emerald-300/30',
        label: 'Healthy',
      }
    }

    if (health >= 70) {
      return {
        text: 'text-yellow-300',
        bar: 'bg-yellow-300',
        ring: 'border-yellow-300/30',
        label: 'Watch',
      }
    }

    return {
      text: 'text-rose-300',
      bar: 'bg-rose-400',
      ring: 'border-rose-300/30',
      label: 'Critical',
    }
  }, [health])

  const statusTone =
    serviceStatus === 'LIVE'
      ? 'border-emerald-300/30 bg-emerald-300/10 text-emerald-200'
      : 'border-rose-300/30 bg-rose-300/10 text-rose-200'

  return (
    <main className="min-h-screen bg-[#11113a] px-5 py-5 text-slate-100">
      <div className="mx-auto flex min-h-[calc(100vh-40px)] max-w-[1760px] flex-col">
        <header className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-[8px] border border-slate-400/20 bg-[#272a61] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]">
              <img src={logo} alt="UpTime.AI logo" className="h-7 w-7 rounded-[4px] object-cover" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-normal text-white">UpTime.AI</h1>
              <p className="text-sm font-medium text-slate-400">Sentry intake and repair console</p>
            </div>
          </div>
          <div className="hidden items-center gap-3 rounded-[8px] border border-slate-300/10 bg-[#232654] px-4 py-3 text-sm text-slate-300 md:flex">
            <span className="h-2 w-2 rounded-full bg-cyan-300" />
            local monitor
          </div>
        </header>

        <section className="grid flex-1 grid-cols-1 gap-5 xl:grid-cols-[0.82fr_1.25fr_1.15fr]">
          <Panel>
            <PanelHeader title="Overall Health" meta={serviceStatus} metaClassName={statusTone} />

            <div className={`mt-5 rounded-[8px] border ${healthTone.ring} bg-[#333469] p-6`}>
              <p className={`text-center text-7xl font-black leading-none tracking-normal ${serviceStatus === 'LIVE' ? 'text-emerald-300' : 'text-rose-300'}`}>
                {serviceStatus}
              </p>
              <p className="mt-4 text-center text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">
                service state
              </p>
            </div>

            <div className="mt-6 space-y-4">
              <label className="block">
                <span className="text-sm font-semibold text-slate-300">Live status</span>
                <select
                  value={serviceStatus}
                  onChange={(event) => setServiceStatus(event.target.value as ServiceStatus)}
                  className="mt-2 h-12 w-full rounded-[6px] border border-slate-300/10 bg-[#17183f] px-4 text-sm font-bold text-white outline-none transition focus:border-cyan-300/60"
                >
                  <option>LIVE</option>
                  <option>DOWN</option>
                </select>
              </label>

              <label className="block">
                <span className="text-sm font-semibold text-slate-300">Overall health tracker</span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={health}
                  onChange={(event) => setHealth(clamp(Number(event.target.value), 0, 100))}
                  className="mt-2 h-12 w-full rounded-[6px] border border-slate-300/10 bg-[#17183f] px-4 text-sm font-bold text-white outline-none transition focus:border-cyan-300/60"
                />
              </label>
            </div>

            <div className="mt-5 rounded-[8px] border border-slate-300/10 bg-[#191a49] p-5">
              <div className="flex items-end justify-between gap-4">
                <p className={`text-6xl font-black leading-none tracking-normal ${healthTone.text}`}>
                  {health}%
                </p>
                <p className="pb-2 text-base font-bold text-slate-200">{healthTone.label}</p>
              </div>
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-900/60">
                <div className={`h-full rounded-full ${healthTone.bar}`} style={{ width: `${health}%` }} />
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Event History" meta={`${events.length} observed`} />
            <p className="mt-4 text-base text-slate-400">
              Exact Sentry events will populate here from the database. Expand an event to inspect the raw stored text.
            </p>

            <div className="mt-6 max-h-[calc(100vh-230px)] space-y-3 overflow-y-auto pr-1">
              {events.map((eventItem) => (
                <ExpandableRow
                  key={eventItem.id}
                  isOpen={openEvent === eventItem.id}
                  onToggle={() => setOpenEvent(openEvent === eventItem.id ? '' : eventItem.id)}
                  title={eventItem.title}
                  subtitle={`${eventItem.route} - ${eventItem.time}`}
                  badge={`${eventItem.code}`}
                  badgeClassName={codeTone(eventItem.code)}
                  meta={eventItem.severity}
                >
                  <pre className="whitespace-pre-wrap rounded-[6px] border border-cyan-300/10 bg-[#101238] p-4 font-mono text-sm leading-relaxed text-slate-200">
                    {eventItem.raw}
                  </pre>
                </ExpandableRow>
              ))}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Recommended Fixes" meta={`${fixes.length} queued`} />
            <p className="mt-4 text-base text-slate-400">
              Patch Agent recommendations will land here with justification and exact code guidance.
            </p>

            <div className="mt-6 max-h-[calc(100vh-230px)] space-y-3 overflow-y-auto pr-1">
              {fixes.map((fix) => (
                <ExpandableRow
                  key={fix.id}
                  isOpen={openFix === fix.id}
                  onToggle={() => setOpenFix(openFix === fix.id ? '' : fix.id)}
                  title={fix.title}
                  subtitle={fix.summary}
                  badge={fix.status}
                  badgeClassName="bg-[#36396d] text-slate-100"
                  meta="patch"
                >
                  <div className="space-y-4">
                    <p className="text-base leading-relaxed text-slate-300">{fix.justification}</p>
                    <pre className="max-h-72 overflow-auto rounded-[6px] border border-cyan-300/10 bg-[#101238] p-4 font-mono text-sm leading-relaxed text-cyan-100">
                      {fix.code}
                    </pre>
                  </div>
                </ExpandableRow>
              ))}
            </div>
          </Panel>
        </section>
      </div>
    </main>
  )
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <section className="min-h-[540px] rounded-[8px] border border-slate-300/10 bg-[#282b5d] p-5 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
      {children}
    </section>
  )
}

function PanelHeader({
  title,
  meta,
  metaClassName = 'border-slate-300/10 bg-[#3a3d70] text-slate-300',
}: {
  title: string
  meta: string
  metaClassName?: string
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-300/10 pb-4">
      <h2 className="text-2xl font-extrabold tracking-normal text-white">{title}</h2>
      <span className={`rounded-full border px-3 py-1 text-sm font-bold ${metaClassName}`}>{meta}</span>
    </div>
  )
}

function ExpandableRow({
  isOpen,
  onToggle,
  title,
  subtitle,
  badge,
  badgeClassName,
  meta,
  children,
}: {
  isOpen: boolean
  onToggle: () => void
  title: string
  subtitle: string
  badge: string
  badgeClassName: string
  meta: string
  children: React.ReactNode
}) {
  return (
    <article className={`rounded-[8px] border bg-[#1a1c49] transition ${isOpen ? 'border-cyan-300/30' : 'border-slate-300/10'}`}>
      <button
        type="button"
        onClick={onToggle}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-4 px-4 py-4 text-left"
        aria-expanded={isOpen}
      >
        <span className="min-w-0">
          <span className="block truncate text-lg font-extrabold tracking-normal text-white">{title}</span>
          <span className="mt-1 block text-sm font-medium text-slate-400">{subtitle}</span>
        </span>
        <span className="flex items-center gap-3">
          <span className={`rounded-full px-3 py-1 text-sm font-black ${badgeClassName}`}>{badge}</span>
          <span className="rounded-[6px] bg-[#343767] px-3 py-2 text-sm font-bold text-slate-100">
            {isOpen ? 'Close' : 'Open'}
          </span>
        </span>
      </button>
      {isOpen && (
        <div className="border-t border-slate-300/10 px-4 pb-4 pt-4">
          <div className="mb-3 text-xs font-black uppercase tracking-[0.18em] text-slate-500">{meta}</div>
          {children}
        </div>
      )}
    </article>
  )
}

function codeTone(code: number) {
  if (code >= 500) {
    return 'bg-rose-300/15 text-rose-200'
  }

  if (code >= 400) {
    return 'bg-yellow-300/15 text-yellow-200'
  }

  return 'bg-emerald-300/15 text-emerald-200'
}

function clamp(value: number, min: number, max: number) {
  if (Number.isNaN(value)) {
    return min
  }

  return Math.min(Math.max(value, min), max)
}

export default App
