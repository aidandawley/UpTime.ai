import { useEffect, useMemo, useState } from 'react'
import logo from './assets/logo.png'

type ServiceStatus = 'LIVE' | 'DOWN'

type Incident = {
  id: number
  sentry_issue_id: string
  title: string
  status: string
  severity: string
  issue_url: string | null
  repo_full_name: string | null
  recommendation: string | null
  pr_url: string | null
  created_at: string
}

type EventItem = {
  id: string
  title: string
  code: number
  time: string
  severity: string
  route: string
  raw: string
}

type HealthScore = {
  score: number
  penalty: number
  windowSize: number
  criticalCount: number
  errorCount: number
  warningCount: number
  lowCount: number
}

type Recommendation = {
  id: number
  incident_id: number
  repo_full_name: string
  title: string
  summary: string
  justification: string
  code_patch: string
  changed_files: string
  tests_to_run: string
  risk: string
  workflow_notes: string
  validation_status: string
  validation_summary: string
  warnings: string
  created_at: string
}

type FixItem = {
  id: string
  incidentId: string
  title: string
  status: string
  summary: string
  justification: string
  code: string
  workflowNotes: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8010'

function App() {
  const serviceStatus: ServiceStatus = 'LIVE'
  const [events, setEvents] = useState<EventItem[]>([])
  const [eventsLoading, setEventsLoading] = useState(true)
  const [eventsError, setEventsError] = useState<string | null>(null)
  const [openEvent, setOpenEvent] = useState('')
  const [fixes, setFixes] = useState<FixItem[]>([])
  const [fixesLoading, setFixesLoading] = useState(true)
  const [fixesError, setFixesError] = useState<string | null>(null)
  const [openFix, setOpenFix] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadEvents() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/incidents/`)

        if (!response.ok) {
          throw new Error(`Incident API returned ${response.status}`)
        }

        const incidents = (await response.json()) as Incident[]
        const nextEvents = incidents.map(incidentToEvent)

        if (!cancelled) {
          setEvents(nextEvents)
          setEventsError(null)
          setOpenEvent((current) => current || nextEvents[0]?.id || '')
        }
      } catch (error) {
        if (!cancelled) {
          setEventsError(error instanceof Error ? error.message : 'Unable to load incidents')
        }
      } finally {
        if (!cancelled) {
          setEventsLoading(false)
        }
      }
    }

    void loadEvents()
    const intervalId = window.setInterval(loadEvents, 4000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadRecommendations() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/recommendations/`)

        if (!response.ok) {
          throw new Error(`Recommendation API returned ${response.status}`)
        }

        const recommendations = (await response.json()) as Recommendation[]
        const nextFixes = recommendations.map(recommendationToFix)

        if (!cancelled) {
          setFixes(nextFixes)
          setFixesError(null)
          setOpenFix((current) => current || nextFixes[0]?.id || '')
        }
      } catch (error) {
        if (!cancelled) {
          setFixesError(error instanceof Error ? error.message : 'Unable to load recommendations')
        }
      } finally {
        if (!cancelled) {
          setFixesLoading(false)
        }
      }
    }

    void loadRecommendations()
    const intervalId = window.setInterval(loadRecommendations, 4000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const healthScore = useMemo(() => calculateHealthScore(events), [events])

  const healthTone = useMemo(() => {
    if (healthScore.score >= 80) {
      return {
        text: 'text-emerald-300',
        bar: 'bg-emerald-400',
        ring: 'border-emerald-300/30',
        label: 'Healthy',
      }
    }

    if (healthScore.score >= 70) {
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
  }, [healthScore.score])

  const statusTone =
    serviceStatus === 'LIVE'
      ? 'border-emerald-300/30 bg-emerald-300/10 text-emerald-200'
      : 'border-rose-300/30 bg-rose-300/10 text-rose-200'

  async function deleteEvent(eventId: string) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/incidents/${eventId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error(`Delete returned ${response.status}`)
      }

      setEvents((current) => current.filter((eventItem) => eventItem.id !== eventId))
      setFixes((current) => current.filter((fix) => fix.incidentId !== eventId))
      setOpenEvent((current) => (current === eventId ? '' : current))
    } catch (error) {
      setEventsError(error instanceof Error ? error.message : 'Unable to delete incident')
    }
  }

  async function deleteFix(fixId: string) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/recommendations/${fixId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error(`Delete returned ${response.status}`)
      }

      setFixes((current) => current.filter((fix) => fix.id !== fixId))
      setOpenFix((current) => (current === fixId ? '' : current))
    } catch (error) {
      setFixesError(error instanceof Error ? error.message : 'Unable to delete recommendation')
    }
  }

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

            <div className="mt-6 rounded-[8px] border border-slate-300/10 bg-[#1f2150] p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-slate-300">Health window</span>
                <span className="rounded-full bg-[#343767] px-3 py-1 text-xs font-black text-slate-200">
                  latest {healthScore.windowSize || 0}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                <HealthStat label="Critical" value={healthScore.criticalCount} tone="text-rose-200" />
                <HealthStat label="Errors" value={healthScore.errorCount} tone="text-orange-200" />
                <HealthStat label="Warnings" value={healthScore.warningCount} tone="text-yellow-200" />
                <HealthStat label="Low" value={healthScore.lowCount} tone="text-slate-300" />
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-slate-300/10 pt-3">
                <span className="text-sm font-semibold text-slate-400">Incident penalty</span>
                <span className="text-sm font-black text-slate-200">-{healthScore.penalty}</span>
              </div>
            </div>

            <div className="mt-5 rounded-[8px] border border-slate-300/10 bg-[#191a49] p-5">
              <div className="flex items-end justify-between gap-4">
                <p className={`text-6xl font-black leading-none tracking-normal ${healthTone.text}`}>
                  {healthScore.score}%
                </p>
                <p className="pb-2 text-base font-bold text-slate-200">{healthTone.label}</p>
              </div>
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-900/60">
                <div className={`h-full rounded-full ${healthTone.bar}`} style={{ width: `${healthScore.score}%` }} />
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Event History" meta={eventsLoading ? 'syncing' : `${events.length} observed`} />
            <p className="mt-4 text-base text-slate-400">
              Exact Sentry events sync from the database. Expand an event to inspect the stored incident text.
            </p>

            <div className="mt-6 max-h-[calc(100vh-230px)] space-y-3 overflow-y-auto pr-1">
              {eventsError && (
                <div className="rounded-[8px] border border-rose-300/20 bg-rose-300/10 px-4 py-3 text-sm font-semibold text-rose-100">
                  Event sync issue: {eventsError}
                </div>
              )}

              {!eventsLoading && !eventsError && events.length === 0 && (
                <div className="rounded-[8px] border border-slate-300/10 bg-[#1a1c49] px-4 py-5 text-sm font-semibold text-slate-300">
                  No incidents have been stored yet.
                </div>
              )}

              {events.map((eventItem) => (
                  <ExpandableRow
                    key={eventItem.id}
                    isOpen={openEvent === eventItem.id}
                    onToggle={() => setOpenEvent(openEvent === eventItem.id ? '' : eventItem.id)}
                    onDelete={() => void deleteEvent(eventItem.id)}
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
            <PanelHeader title="Recommended Fixes" meta={fixesLoading ? 'syncing' : `${fixes.length} queued`} />
            <p className="mt-4 text-base text-slate-400">
              Patch Agent recommendations will land here with justification and exact code guidance.
            </p>

            <div className="mt-6 max-h-[calc(100vh-230px)] space-y-3 overflow-y-auto pr-1">
              {fixesError && (
                <div className="rounded-[8px] border border-rose-300/20 bg-rose-300/10 px-4 py-3 text-sm font-semibold text-rose-100">
                  Recommendation sync issue: {fixesError}
                </div>
              )}

              {!fixesLoading && !fixesError && fixes.length === 0 && (
                <div className="rounded-[8px] border border-slate-300/10 bg-[#1a1c49] px-4 py-5 text-sm font-semibold text-slate-300">
                  No validated recommendations have been stored yet.
                </div>
              )}

              {fixes.map((fix) => (
                <ExpandableRow
                  key={fix.id}
                  isOpen={openFix === fix.id}
                  onToggle={() => setOpenFix(openFix === fix.id ? '' : fix.id)}
                  onDelete={() => void deleteFix(fix.id)}
                  title={fix.title}
                  subtitle={fix.summary}
                  badge={fix.status}
                  badgeClassName={fixTone(fix.status)}
                  meta="patch"
                >
                  <div className="space-y-4">
                    <p className="text-base leading-relaxed text-slate-300">{fix.justification}</p>
                    <pre className="max-h-72 overflow-auto rounded-[6px] border border-cyan-300/10 bg-[#101238] p-4 font-mono text-sm leading-relaxed text-cyan-100">
                      {fix.code}
                    </pre>
                    {fix.workflowNotes && (
                      <div className="rounded-[6px] border border-slate-300/10 bg-[#222554] p-4">
                        <div className="mb-2 text-xs font-black uppercase tracking-[0.18em] text-slate-500">
                          Workflow Notes
                        </div>
                        <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-300">
                          {fix.workflowNotes}
                        </pre>
                      </div>
                    )}
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

function HealthStat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-[6px] border border-slate-300/10 bg-[#17183f] px-3 py-3">
      <div className={`text-xl font-black leading-none ${tone}`}>{value}</div>
      <div className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</div>
    </div>
  )
}

function ExpandableRow({
  isOpen,
  onToggle,
  onDelete,
  title,
  subtitle,
  badge,
  badgeClassName,
  meta,
  children,
}: {
  isOpen: boolean
  onToggle: () => void
  onDelete: () => void
  title: string
  subtitle: string
  badge: string
  badgeClassName: string
  meta: string
  children: React.ReactNode
}) {
  return (
    <article className={`rounded-[8px] border bg-[#1a1c49] transition ${isOpen ? 'border-cyan-300/30' : 'border-slate-300/10'}`}>
      <div className="grid w-full grid-cols-[1fr_auto] items-center gap-4 px-4 py-4">
        <button type="button" onClick={onToggle} className="min-w-0 text-left" aria-expanded={isOpen}>
          <span className="block truncate text-lg font-extrabold tracking-normal text-white">{title}</span>
          <span className="mt-1 block text-sm font-medium text-slate-400">{subtitle}</span>
        </button>
        <div className="flex items-center gap-3">
          <span className={`rounded-full px-3 py-1 text-sm font-black ${badgeClassName}`}>{badge}</span>
          <button
            type="button"
            onClick={onToggle}
            className="rounded-[6px] bg-[#343767] px-3 py-2 text-sm font-bold text-slate-100 transition hover:bg-[#43477f]"
            aria-expanded={isOpen}
          >
            {isOpen ? 'Close' : 'Open'}
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded-[6px] border border-rose-300/20 bg-rose-300/10 px-3 py-2 text-sm font-bold text-rose-100 transition hover:bg-rose-300/20"
          >
            Delete
          </button>
        </div>
      </div>
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

function incidentToEvent(incident: Incident): EventItem {
  const code = codeFromIncident(incident)

  return {
    id: String(incident.id),
    title: incident.title || 'Untitled incident',
    code,
    time: relativeTime(incident.created_at),
    severity: incident.severity || 'unknown',
    route: incident.status,
    raw: [
      `incident_id: ${incident.id}`,
      `sentry_issue_id: ${incident.sentry_issue_id}`,
      `title: ${incident.title}`,
      `status: ${incident.status}`,
      `severity: ${incident.severity}`,
      `repo_full_name: ${incident.repo_full_name ?? 'none'}`,
      `issue_url: ${incident.issue_url ?? 'none'}`,
      `created_at: ${incident.created_at}`,
      incident.recommendation ? `recommendation:\n${incident.recommendation}` : null,
    ]
      .filter(Boolean)
      .join('\n'),
  }
}

function recommendationToFix(recommendation: Recommendation): FixItem {
  const metadata = [
    `incident_id: ${recommendation.incident_id}`,
    `repo_full_name: ${recommendation.repo_full_name}`,
    `changed_files:\n${recommendation.changed_files || 'none'}`,
    `tests_to_run:\n${recommendation.tests_to_run || 'none'}`,
    `validation_summary: ${recommendation.validation_summary}`,
    recommendation.warnings ? `warnings:\n${recommendation.warnings}` : null,
  ]
    .filter(Boolean)
    .join('\n\n')

  return {
    id: String(recommendation.id),
    incidentId: String(recommendation.incident_id),
    title: recommendation.title || `Recommendation for incident ${recommendation.incident_id}`,
    status: recommendation.validation_status,
    summary: recommendation.summary || recommendation.validation_summary,
    justification: [recommendation.justification, metadata].filter(Boolean).join('\n\n'),
    code: recommendation.code_patch,
    workflowNotes: recommendation.workflow_notes,
  }
}

function codeFromIncident(incident: Incident) {
  const text = `${incident.title} ${incident.status} ${incident.severity} ${incident.recommendation ?? ''}`.toLowerCase()

  if (text.includes('404') || text.includes('not found') || text.includes('bogus')) {
    return 404
  }

  if (text.includes('401') || text.includes('unauthorized')) {
    return 401
  }

  if (incident.severity === 'warning') {
    return 400
  }

  if (['error', 'fatal', 'high', 'critical'].includes(incident.severity)) {
    return 500
  }

  return 200
}

function calculateHealthScore(events: EventItem[]): HealthScore {
  const windowedEvents = events.slice(0, 10)
  let penalty = 0
  let criticalCount = 0
  let errorCount = 0
  let warningCount = 0
  let lowCount = 0

  for (const eventItem of windowedEvents) {
    const severity = eventItem.severity.toLowerCase()
    const text = `${eventItem.title} ${eventItem.route} ${severity}`.toLowerCase()

    if (eventItem.code >= 500 || ['fatal', 'critical', 'high'].includes(severity)) {
      penalty += 25
      criticalCount += 1
    } else if (['error', 'medium'].includes(severity) || text.includes('exception')) {
      penalty += 15
      errorCount += 1
    } else if (eventItem.code >= 400 || ['warning', 'warn'].includes(severity)) {
      penalty += 7
      warningCount += 1
    } else {
      penalty += 3
      lowCount += 1
    }
  }

  return {
    score: clamp(100 - penalty, 0, 100),
    penalty,
    windowSize: windowedEvents.length,
    criticalCount,
    errorCount,
    warningCount,
    lowCount,
  }
}

function fixTone(status: string) {
  if (status === 'approved') {
    return 'bg-emerald-300/15 text-emerald-200'
  }

  if (status === 'needs_review') {
    return 'bg-yellow-300/15 text-yellow-200'
  }

  return 'bg-[#36396d] text-slate-100'
}

function relativeTime(value: string) {
  const timestamp = new Date(value).getTime()

  if (Number.isNaN(timestamp)) {
    return 'unknown time'
  }

  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))

  if (seconds < 60) {
    return `${seconds}s ago`
  }

  const minutes = Math.floor(seconds / 60)

  if (minutes < 60) {
    return `${minutes}m ago`
  }

  const hours = Math.floor(minutes / 60)

  if (hours < 24) {
    return `${hours}h ago`
  }

  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function clamp(value: number, min: number, max: number) {
  if (Number.isNaN(value)) {
    return min
  }

  return Math.min(Math.max(value, min), max)
}

export default App
