import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000/api'

function Statistics() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadStatistics()
  }, [])

  const loadStatistics = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/stats`)
      if (!res.ok) throw new Error('Failed to load statistics')
      const data = await res.json()
      setStats(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="statistics">
        <div className="loading">Loading statistics...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="statistics">
        <div className="error">Error: {error}</div>
        <button onClick={loadStatistics}>Retry</button>
      </div>
    )
  }

  if (!stats) return null

  return (
    <div className="statistics">
      <div className="stats-header">
        <h2>Database Statistics</h2>
        <button onClick={loadStatistics} className="refresh-button">
          Refresh
        </button>
      </div>

      {/* Overview Cards */}
      <div className="stats-section">
        <h3>Overview</h3>
        <div className="stats-grid-4">
          <div className="stat-card">
            <div className="stat-value">{stats.overview.total_products.toLocaleString()}</div>
            <div className="stat-label">Total Products</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.overview.added_today.toLocaleString()}</div>
            <div className="stat-label">Added Today</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.overview.added_this_week.toLocaleString()}</div>
            <div className="stat-label">Added This Week</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.overview.added_this_month.toLocaleString()}</div>
            <div className="stat-label">Added This Month</div>
          </div>
        </div>
      </div>

      {/* Data Quality */}
      <div className="stats-section">
        <h3>Data Quality</h3>
        <div className="stats-grid-5">
          <div className="stat-card">
            <div className="stat-value">{stats.data_quality.has_isin.percentage}%</div>
            <div className="stat-label">Has ISIN</div>
            <div className="stat-count">{stats.data_quality.has_isin.count.toLocaleString()} products</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.data_quality.has_maturity.percentage}%</div>
            <div className="stat-label">Has Maturity</div>
            <div className="stat-count">{stats.data_quality.has_maturity.count.toLocaleString()} products</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.data_quality.has_coupon.percentage}%</div>
            <div className="stat-label">Has Coupon</div>
            <div className="stat-count">{stats.data_quality.has_coupon.count.toLocaleString()} products</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.data_quality.has_underlyings.percentage}%</div>
            <div className="stat-label">Has Underlyings</div>
            <div className="stat-count">{stats.data_quality.has_underlyings.count.toLocaleString()} products</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.data_quality.has_barrier.percentage}%</div>
            <div className="stat-label">Has Barrier</div>
            <div className="stat-count">{stats.data_quality.has_barrier.count.toLocaleString()} products</div>
          </div>
        </div>
      </div>

      {/* Products by Source */}
      <div className="stats-section">
        <h3>Products by Source</h3>
        <div className="stats-table">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Count</th>
                <th>Percentage</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_source.map((item) => (
                <tr key={item.source}>
                  <td className="source-name">{item.source.replace('_', ' ')}</td>
                  <td>{item.count.toLocaleString()}</td>
                  <td>
                    <div className="percentage-bar">
                      <div
                        className="percentage-fill"
                        style={{
                          width: `${(item.count / stats.overview.total_products) * 100}%`
                        }}
                      />
                      <span className="percentage-text">
                        {((item.count / stats.overview.total_products) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Products by Type */}
      <div className="stats-section">
        <h3>Top Product Types</h3>
        <div className="stats-table">
          <table>
            <thead>
              <tr>
                <th>Product Type</th>
                <th>Count</th>
                <th>Percentage</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_type.map((item) => (
                <tr key={item.type}>
                  <td className="product-type">{item.type}</td>
                  <td>{item.count.toLocaleString()}</td>
                  <td>
                    <div className="percentage-bar">
                      <div
                        className="percentage-fill"
                        style={{
                          width: `${(item.count / stats.overview.total_products) * 100}%`
                        }}
                      />
                      <span className="percentage-text">
                        {((item.count / stats.overview.total_products) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="stats-row">
        {/* Products by Currency */}
        <div className="stats-section half">
          <h3>Products by Currency</h3>
          <div className="stats-list">
            {stats.by_currency.slice(0, 10).map((item) => (
              <div key={item.currency} className="stats-list-item">
                <span className="stats-list-label">{item.currency}</span>
                <span className="stats-list-value">{item.count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Products by Issuer */}
        <div className="stats-section half">
          <h3>Top Issuers</h3>
          <div className="stats-list">
            {stats.by_issuer.map((item) => (
              <div key={item.issuer} className="stats-list-item">
                <span className="stats-list-label">{item.issuer}</span>
                <span className="stats-list-value">{item.count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Review Status */}
      <div className="stats-section">
        <h3>Review Status</h3>
        <div className="stats-grid-auto">
          {stats.by_review_status.map((item) => (
            <div key={item.status} className="stat-card">
              <div className="stat-value">{item.count.toLocaleString()}</div>
              <div className="stat-label">{item.status.replace('_', ' ')}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Maturity Distribution */}
      <div className="stats-section">
        <h3>Maturity Distribution</h3>
        <div className="stats-table">
          <table>
            <thead>
              <tr>
                <th>Time to Maturity</th>
                <th>Count</th>
                <th>Percentage</th>
              </tr>
            </thead>
            <tbody>
              {stats.maturity_distribution.map((item) => (
                <tr key={item.bucket}>
                  <td className="maturity-bucket">{item.bucket}</td>
                  <td>{item.count.toLocaleString()}</td>
                  <td>
                    <div className="percentage-bar">
                      <div
                        className="percentage-fill"
                        style={{
                          width: `${(item.count / stats.overview.total_products) * 100}%`
                        }}
                      />
                      <span className="percentage-text">
                        {((item.count / stats.overview.total_products) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Crawl Summary */}
      <div className="stats-section">
        <h3>Crawl Activity Summary</h3>
        <div className="stats-grid-auto">
          {stats.crawl_summary.map((item) => (
            <div key={item.status} className="stat-card">
              <div className="stat-value">{item.count.toLocaleString()}</div>
              <div className="stat-label">{item.status} crawls</div>
              <div className="stat-count">
                {item.total_completed?.toLocaleString() || 0} products · {item.total_errors || 0} errors
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Crawl Activity */}
      <div className="stats-section">
        <h3>Recent Crawl Activity</h3>
        <div className="stats-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Errors</th>
                <th>Started</th>
                <th>Ended</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_crawl_activity.map((item, idx) => (
                <tr key={idx}>
                  <td className="crawl-name">{item.name}</td>
                  <td>
                    <span className={`status-pill status-${item.status}`}>{item.status}</span>
                  </td>
                  <td>
                    {item.completed.toLocaleString()}/{item.total?.toLocaleString() || '?'}
                  </td>
                  <td>{item.errors}</td>
                  <td className="timestamp">{new Date(item.started_at).toLocaleString()}</td>
                  <td className="timestamp">
                    {item.ended_at ? new Date(item.ended_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default Statistics
