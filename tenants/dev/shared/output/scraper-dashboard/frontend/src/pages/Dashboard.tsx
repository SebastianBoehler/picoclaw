import { useEffect, useState } from 'react'
import { API_BASE } from '../config'
import './Dashboard.css'

interface Stats {
  total_records: number
  active_adapters: number
  last_scraped: string | null
  recent_jobs: any[]
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState<Record<string, boolean>>({})

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/stats`)
      const data = await res.json()
      setStats(data)
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    } finally {
      setLoading(false)
    }
  }

  const triggerScrape = async (adapter: string) => {
    setTriggering(prev => ({ ...prev, [adapter]: true }))
    try {
      const res = await fetch(`${API_BASE}/scrape/${adapter}`, { method: 'POST' })
      if (res.ok) {
        alert(`Scrape started for ${adapter}`)
        fetchStats()
      } else {
        alert(`Failed to trigger scrape for ${adapter}`)
      }
    } catch (e) {
      alert(`Error: ${e}`)
    } finally {
      setTriggering(prev => ({ ...prev, [adapter]: false }))
    }
  }

  if (loading) return <div className="loading">Loading...</div>

  const adapters = ['reddit', 'hackernews', 'coingecko']

  return (
    <div className="dashboard">
      <h1>Dashboard</h1>
      
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Records</h3>
          <p className="stat-value">{stats?.total_records.toLocaleString()}</p>
        </div>
        <div className="stat-card">
          <h3>Active Adapters</h3>
          <p className="stat-value">{stats?.active_adapters}</p>
        </div>
        <div className="stat-card">
          <h3>Last Scraped</h3>
          <p className="stat-value">{stats?.last_scraped 
            ? new Date(stats.last_scraped).toLocaleString() 
            : 'Never'
          }</p>
        </div>
      </div>

      <h2>Quick Actions</h2>
      <div className="actions-grid">
        {adapters.map(adapter => (
          <div key={adapter} className="action-card">
            <h4>{adapter.charAt(0).toUpperCase() + adapter.slice(1)}</h4>
            <button 
              onClick={() => triggerScrape(adapter)}
              disabled={triggering[adapter]}
            >
              {triggering[adapter] ? 'Scraping...' : 'Scrape Now'}
            </button>
          </div>
        ))}
      </div>

      <h2>Recent Jobs</h2>
      <div className="jobs-list">
        {stats?.recent_jobs?.length === 0 ? (
          <p>No jobs yet</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Adapter</th>
                <th>Status</th>
                <th>Records</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {stats?.recent_jobs?.slice(0, 5).map((job: any) => (
                <tr key={job.id}>
                  <td>{job.id.slice(0, 8)}</td>
                  <td>{job.adapter}</td>
                  <td>
                    <span className={`status ${job.status}`}>{job.status}</span>
                  </td>
                  <td>{job.records_count}</td>
                  <td>{new Date(job.started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
