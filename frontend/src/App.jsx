import { useState, useEffect, useRef } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const COMPANY_TEMPLATES = [
  'Extract headquarters, business units, core products, target industries, key executives, and recent strategic initiatives. Return structured JSON.',
  'Find all available information about digital transformation initiatives, ERP implementations, and AI projects. Include evidence links.',
  'Identify key decision makers, recent expansions, and investment activities. Focus on verifiable public sources.',
]

const GEO_TEMPLATES = [
  'Extract headquarters, business units, core products, target industries, key executives, and recent strategic initiatives. Return structured JSON.',
  'Focus on companies with active digital transformation or ERP modernization programs.',
  'Identify companies with recent funding, expansion, or strategic partnership announcements.',
]

function StatusBadge({ status }) {
  const colors = {
    queued: '#f59e0b',
    processing: '#3b82f6',
    completed: '#10b981',
    failed: '#ef4444',
  }
  const labels = {
    queued: '⏳ Queued',
    processing: '⚙️ Processing',
    completed: '✅ Completed',
    failed: '❌ Failed',
  }
  return (
    <span style={{
      display: 'inline-block',
      padding: '4px 12px',
      borderRadius: '20px',
      backgroundColor: colors[status] || '#6b7280',
      color: 'white',
      fontSize: '0.85rem',
      fontWeight: '600',
    }}>
      {labels[status] || status}
    </span>
  )
}

function ProgressBar({ status }) {
  if (status === 'completed') return <div style={{ height: '4px', background: '#10b981', borderRadius: '2px' }} />
  if (status === 'failed') return <div style={{ height: '4px', background: '#ef4444', borderRadius: '2px' }} />
  if (status === 'processing') {
    return (
      <div style={{ height: '4px', background: '#e5e7eb', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          background: '#3b82f6',
          borderRadius: '2px',
          animation: 'progress-slide 1.5s infinite',
          width: '40%',
        }} />
      </div>
    )
  }
  return <div style={{ height: '4px', background: '#e5e7eb', borderRadius: '2px' }} />
}

function ResultTabs({ result, jobType }) {
  const [activeTab, setActiveTab] = useState('json')
  const jsonStr = JSON.stringify(result, null, 2)
  const mdContent = generateMarkdown(result, jobType)

  return (
    <div>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', borderBottom: '2px solid #e5e7eb' }}>
        {['json', 'markdown'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 20px',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              fontWeight: '600',
              fontSize: '0.9rem',
              color: activeTab === tab ? '#2563eb' : '#6b7280',
              borderBottom: activeTab === tab ? '2px solid #2563eb' : '2px solid transparent',
              marginBottom: '-2px',
              transition: 'all 0.2s',
            }}
          >
            {tab === 'json' ? '{ } JSON' : '📄 Markdown'}
          </button>
        ))}
      </div>

      {activeTab === 'json' && (
        <pre style={{
          background: '#1e293b',
          color: '#e2e8f0',
          padding: '20px',
          borderRadius: '8px',
          overflow: 'auto',
          fontSize: '0.8rem',
          maxHeight: '500px',
          lineHeight: '1.5',
        }}>
          {jsonStr}
        </pre>
      )}

      {activeTab === 'markdown' && (
        <div style={{
          background: '#f8fafc',
          padding: '20px',
          borderRadius: '8px',
          overflow: 'auto',
          maxHeight: '500px',
          fontSize: '0.9rem',
          lineHeight: '1.8',
          fontFamily: 'Georgia, serif',
        }}>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0 }}>
            {mdContent}
          </pre>
        </div>
      )}
    </div>
  )
}

function generateMarkdown(result, jobType) {
  if (!result) return ''

  if (jobType === 'geography' && result.companies_found) {
    let md = `# Geography Intelligence Report: ${result.location}\n`
    md += `**Criteria**: ${result.criteria}\n\n`
    if (result.companies_found?.length) {
      md += `## Companies Discovered\n${result.companies_found.map(c => `- ${c}`).join('\n')}\n\n`
    }
    result.reports?.forEach(r => {
      md += generateCompanyMarkdown(r) + '\n\n---\n\n'
    })
    return md
  }

  return generateCompanyMarkdown(result)
}

function generateCompanyMarkdown(report) {
  if (!report) return ''
  const id = report.company_identifiers || {}
  const snap = report.business_snapshot || {}
  const lead = report.leadership_signals || {}
  const init = report.strategic_initiatives || {}
  const ev = report.evidence_sources || []

  let md = `# Intelligence Report: ${id.name || 'Unknown'}\n\n`
  md += `## Company Identifiers\n`
  if (id.headquarters) md += `- **HQ**: ${id.headquarters}\n`
  if (id.website) md += `- **Website**: ${id.website}\n`
  if (id.industry) md += `- **Industry**: ${id.industry}\n`
  md += '\n'

  if (snap.business_units?.length) {
    md += `## Business Units\n${snap.business_units.map(u => `- ${u}`).join('\n')}\n\n`
  }
  if (snap.products_and_services?.length) {
    md += `## Products & Services\n${snap.products_and_services.map(p => `- ${p}`).join('\n')}\n\n`
  }

  if (lead.executives?.length) {
    md += `## Leadership\n${lead.executives.map(e => `- **${e.name}** — ${e.title}`).join('\n')}\n\n`
  }

  const initSections = [
    ['transformation', 'Transformation'],
    ['ai_initiatives', 'AI Initiatives'],
    ['investments', 'Investments'],
    ['expansions', 'Expansions'],
  ]
  const hasInit = initSections.some(([k]) => init[k]?.length)
  if (hasInit) {
    md += `## Strategic Initiatives\n`
    initSections.forEach(([key, label]) => {
      if (init[key]?.length) {
        md += `### ${label}\n${init[key].map(i => `- ${i}`).join('\n')}\n\n`
      }
    })
  }

  if (ev.length) {
    md += `## Evidence Sources\n${ev.map((s, i) => `${i + 1}. [${s.title || s.url}](${s.url})`).join('\n')}\n`
  }

  return md
}

export default function App() {
  const [mode, setMode] = useState('company')
  const [companyName, setCompanyName] = useState('')
  const [location, setLocation] = useState('')
  const [criteria, setCriteria] = useState('')
  const [topN, setTopN] = useState(3)
  const [objectivePrompt, setObjectivePrompt] = useState(COMPANY_TEMPLATES[0])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [error, setError] = useState(null)
  const pollingRef = useRef(null)

  useEffect(() => {
    setObjectivePrompt(mode === 'company' ? COMPANY_TEMPLATES[0] : GEO_TEMPLATES[0])
  }, [mode])

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`)
        if (!res.ok) throw new Error('Failed to fetch job status')
        const data = await res.json()
        setJobStatus(data)

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollingRef.current)
        }
      } catch (err) {
        setError('Failed to fetch job status. Is the backend running?')
        clearInterval(pollingRef.current)
      }
    }

    poll()
    pollingRef.current = setInterval(poll, 2000)
    return () => clearInterval(pollingRef.current)
  }, [jobId])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setJobId(null)
    setJobStatus(null)
    setIsSubmitting(true)

    try {
      let endpoint, body
      if (mode === 'company') {
        endpoint = `${API_BASE}/api/jobs/company`
        body = { company_name: companyName, objective_prompt: objectivePrompt }
      } else {
        endpoint = `${API_BASE}/api/jobs/geography`
        body = { location, criteria, objective_prompt: objectivePrompt, top_n: topN }
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setJobId(data.job_id)
    } catch (err) {
      setError(err.message || 'Failed to submit job. Check that the backend is running.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDownload = async (format) => {
    if (!jobId) return
    const url = `${API_BASE}/api/jobs/${jobId}/download/${format}`
    const a = document.createElement('a')
    a.href = url
    a.download = `intelligence_report.${format === 'markdown' ? 'md' : format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const isCompleted = jobStatus?.status === 'completed'
  const isProcessing = jobStatus?.status === 'processing' || jobStatus?.status === 'queued'

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <header style={{
        background: 'rgba(255,255,255,0.1)',
        backdropFilter: 'blur(10px)',
        padding: '16px 32px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        borderBottom: '1px solid rgba(255,255,255,0.2)',
      }}>
        <div style={{ fontSize: '2rem' }}>🎯</div>
        <div>
          <h1 style={{ margin: 0, color: 'white', fontSize: '1.5rem', fontWeight: '700' }}>
            Account Intelligence Radar
          </h1>
          <p style={{ margin: 0, color: 'rgba(255,255,255,0.8)', fontSize: '0.85rem' }}>
            AI-powered business intelligence for outreach
          </p>
        </div>
      </header>

      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '32px 16px' }}>
        <div style={{
          background: 'white',
          borderRadius: '16px',
          padding: '32px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
          marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', gap: '12px', marginBottom: '28px' }}>
            {[
              { value: 'company', label: '🏢 Company Mode', desc: 'Research a specific company' },
              { value: 'geography', label: '🌍 Geography Mode', desc: 'Discover companies in a region' },
            ].map(opt => (
              <button
                key={opt.value}
                onClick={() => setMode(opt.value)}
                style={{
                  flex: 1,
                  padding: '14px 20px',
                  border: '2px solid',
                  borderColor: mode === opt.value ? '#2563eb' : '#e5e7eb',
                  borderRadius: '10px',
                  background: mode === opt.value ? '#eff6ff' : 'white',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ fontWeight: '700', color: mode === opt.value ? '#2563eb' : '#374151', fontSize: '1rem' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '2px' }}>{opt.desc}</div>
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit}>
            {mode === 'company' && (
              <div style={{ marginBottom: '20px' }}>
                <label style={labelStyle}>Company Name *</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={e => setCompanyName(e.target.value)}
                  placeholder="e.g. Saudi Aramco, ACWA Power, Almarai"
                  required
                  style={inputStyle}
                />
              </div>
            )}

            {mode === 'geography' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                <div>
                  <label style={labelStyle}>Location *</label>
                  <input
                    type="text"
                    value={location}
                    onChange={e => setLocation(e.target.value)}
                    placeholder="e.g. Saudi Arabia, Riyadh, KSA"
                    required
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Sector Criteria *</label>
                  <input
                    type="text"
                    value={criteria}
                    onChange={e => setCriteria(e.target.value)}
                    placeholder="e.g. energy, manufacturing, logistics"
                    required
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Top N Companies</label>
                  <input
                    type="number"
                    value={topN}
                    onChange={e => setTopN(Number(e.target.value))}
                    min={1}
                    max={10}
                    style={inputStyle}
                  />
                </div>
              </div>
            )}

            <div style={{ marginBottom: '20px' }}>
              <label style={labelStyle}>Objective Prompt</label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                {(mode === 'company' ? COMPANY_TEMPLATES : GEO_TEMPLATES).map((t, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setObjectivePrompt(t)}
                    style={{
                      padding: '4px 10px',
                      fontSize: '0.75rem',
                      border: '1px solid',
                      borderColor: objectivePrompt === t ? '#2563eb' : '#d1d5db',
                      borderRadius: '20px',
                      background: objectivePrompt === t ? '#eff6ff' : 'white',
                      color: objectivePrompt === t ? '#2563eb' : '#6b7280',
                      cursor: 'pointer',
                    }}
                  >
                    Template {i + 1}
                  </button>
                ))}
              </div>
              <textarea
                value={objectivePrompt}
                onChange={e => setObjectivePrompt(e.target.value)}
                rows={3}
                style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
              />
            </div>

            {error && (
              <div style={{
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '16px',
                color: '#dc2626',
                fontSize: '0.9rem',
              }}>
                ⚠️ {error}
                {error.includes('402') && (
                  <div style={{ marginTop: '8px', fontSize: '0.85rem' }}>
                    💡 <strong>Tip:</strong> Check your API key balance at the provider dashboard.
                  </div>
                )}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting || isProcessing}
              style={{
                width: '100%',
                padding: '14px',
                background: isSubmitting || isProcessing
                  ? '#9ca3af'
                  : 'linear-gradient(135deg, #2563eb, #7c3aed)',
                color: 'white',
                border: 'none',
                borderRadius: '10px',
                fontSize: '1rem',
                fontWeight: '700',
                cursor: isSubmitting || isProcessing ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {isSubmitting ? '⏳ Submitting...'
                : isProcessing ? '⚙️ Processing...'
                : '🚀 Generate Intelligence Report'}
            </button>
          </form>
        </div>

        {jobId && jobStatus && (
          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '24px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
            marginBottom: '24px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h2 style={{ margin: 0, fontSize: '1.1rem', color: '#1e293b' }}>Job Status</h2>
              <StatusBadge status={jobStatus.status} />
            </div>
            <ProgressBar status={jobStatus.status} />
            <p style={{ margin: '12px 0 4px', color: '#475569', fontSize: '0.9rem' }}>
              {jobStatus.message}
            </p>
            {jobStatus.progress && (
              <p style={{ margin: 0, color: '#6b7280', fontSize: '0.85rem', fontStyle: 'italic' }}>
                → {jobStatus.progress}
              </p>
            )}
            {jobStatus.error && (
              <div style={{
                marginTop: '12px',
                padding: '10px 14px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '6px',
                color: '#dc2626',
                fontSize: '0.85rem',
              }}>
                {jobStatus.error}
                {jobStatus.error.includes('402') && (
                  <div style={{ marginTop: '6px' }}>
                    💡 Please top up your API balance and try again.
                  </div>
                )}
              </div>
            )}
            <p style={{ margin: '12px 0 0', color: '#94a3b8', fontSize: '0.75rem' }}>
              Job ID: {jobId}
            </p>
          </div>
        )}

        {isCompleted && jobStatus?.result && (
          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '24px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#1e293b' }}>
                📊 Intelligence Report
              </h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                {['json', 'markdown', 'csv'].map(fmt => (
                  <button
                    key={fmt}
                    onClick={() => handleDownload(fmt)}
                    style={{
                      padding: '8px 16px',
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      fontWeight: '600',
                      color: '#475569',
                      transition: 'all 0.2s',
                    }}
                  >
                    ⬇️ {fmt.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <ResultTabs result={jobStatus.result} jobType={mode} />
          </div>
        )}

        <div style={{ textAlign: 'center', marginTop: '32px', color: 'rgba(255,255,255,0.7)', fontSize: '0.8rem' }}>
          Account Intelligence Radar v1.0 · Powered by SerpAPI, DeepSeek &amp; Firecrawl
        </div>
      </div>
    </div>
  )
}

const labelStyle = {
  display: 'block',
  marginBottom: '6px',
  fontWeight: '600',
  color: '#374151',
  fontSize: '0.9rem',
}

const inputStyle = {
  width: '100%',
  padding: '10px 14px',
  border: '2px solid #e5e7eb',
  borderRadius: '8px',
  fontSize: '0.9rem',
  outline: 'none',
  transition: 'border-color 0.2s',
  boxSizing: 'border-box',
}
