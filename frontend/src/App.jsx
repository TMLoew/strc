import { useEffect, useMemo, useState } from 'react'
import Statistics from './Statistics.jsx'

const API_BASE = 'http://localhost:8000/api'

function App() {
  const [products, setProducts] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [detail, setDetail] = useState(null)
  const [compare, setCompare] = useState(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [bestMode, setBestMode] = useState(false)
  const [crawlStatus, setCrawlStatus] = useState('')
  const [crawlErrors, setCrawlErrors] = useState([])
  const [crawlRunning, setCrawlRunning] = useState(false)
  const [portalRunning, setPortalRunning] = useState(false)
  const [portalStatus, setPortalStatus] = useState('')
  const [portalErrors, setPortalErrors] = useState([])
  const [scannerRunning, setScannerRunning] = useState(false)
  const [scannerStatus, setScannerStatus] = useState('')
  const [scannerErrors, setScannerErrors] = useState([])
  const [portalProgress, setPortalProgress] = useState({ completed: 0, total: 0 })
  const [scannerProgress, setScannerProgress] = useState({ completed: 0, total: 0 })
  const [detailTab, setDetailTab] = useState('detail')
  const [sqUser, setSqUser] = useState('')
  const [sqPass, setSqPass] = useState('')
  const [sqSessionStatus, setSqSessionStatus] = useState('')
  const [ltSessionStatus, setLtSessionStatus] = useState('')
  const [ltApiRunning, setLtApiRunning] = useState(false)
  const [ltApiStatus, setLtApiStatus] = useState('')
  const [ltApiProgress, setLtApiProgress] = useState({ completed: 0, total: 0 })
  const [enrichRunning, setEnrichRunning] = useState(false)
  const [enrichStatus, setEnrichStatus] = useState('')
  const [enrichProgress, setEnrichProgress] = useState({ enriched: 0, failed: 0, processed: 0 })
  const [enrichLimit, setEnrichLimit] = useState(100)
  const [enrichFilter, setEnrichFilter] = useState('missing_any')
  const [finanzenRunning, setFinanzenRunning] = useState(false)
  const [finanzenStatus, setFinanzenStatus] = useState('')
  const [finanzenProgress, setFinanzenProgress] = useState({ enriched: 0, failed: 0, processed: 0 })
  const [finanzenLimit, setFinanzenLimit] = useState(100)
  const [finanzenFilter, setFinanzenFilter] = useState('missing_coupon')
  const [autoEnrichRunning, setAutoEnrichRunning] = useState(false)
  const [autoEnrichStatus, setAutoEnrichStatus] = useState(null)
  const [autoEnrichBatchSize, setAutoEnrichBatchSize] = useState(10)
  const [clearStatus, setClearStatus] = useState('')
  const [openProfiles, setOpenProfiles] = useState({})
  const [sourceFilter, setSourceFilter] = useState('All')
  const [productTypeFilter, setProductTypeFilter] = useState('All')
  const [issuerFilter, setIssuerFilter] = useState('All')
  const [currencyFilter, setCurrencyFilter] = useState('All')
  const [ratingFilter, setRatingFilter] = useState('All')
  const [wtyFilter, setWtyFilter] = useState('All')
  const [ytmFilter, setYtmFilter] = useState('All')
  const [couponFilter, setCouponFilter] = useState('All')
  const [barrierFilter, setBarrierFilter] = useState('All')
  const [issueDateFilter, setIssueDateFilter] = useState('All')
  const [mainTab, setMainTab] = useState('products')
  const [sourceOptions, setSourceOptions] = useState([])
  const [productTypeOptions, setProductTypeOptions] = useState([])
  const [serverTotal, setServerTotal] = useState(0)

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const loadProducts = async () => {
    let endpoint = bestMode
      ? `${API_BASE}/products/best?limit=50`
      : `${API_BASE}/products?limit=200&offset=0`

    // Add filters for non-best mode
    if (!bestMode) {
      const params = new URLSearchParams()
      params.set('limit', '200')
      params.set('offset', '0')
      if (sourceFilter !== 'All') params.set('source', sourceFilter)
      if (productTypeFilter !== 'All') params.set('product_type', productTypeFilter)
      endpoint = `${API_BASE}/products?${params.toString()}`
    }

    const res = await fetch(endpoint)
    const data = await res.json()
    setProducts(bestMode ? data.products : data.items)
    if (!bestMode && data.total !== undefined) {
      setServerTotal(data.total)
    }
  }

  const loadFilterOptions = async () => {
    // Load source options
    const sourcesRes = await fetch(`${API_BASE}/products/filters/sources`)
    const sourcesData = await sourcesRes.json()
    setSourceOptions(sourcesData.sources)

    // Load product type options (filtered by source if selected)
    const typeParams = sourceFilter !== 'All' ? `?source=${sourceFilter}` : ''
    const typesRes = await fetch(`${API_BASE}/products/filters/product-types${typeParams}`)
    const typesData = await typesRes.json()
    setProductTypeOptions(typesData.product_types)
  }

  const loadDetail = async (id) => {
    const res = await fetch(`${API_BASE}/products/${id}`)
    const data = await res.json()
    setDetail(data)
  }

  const loadCompare = async () => {
    if (selectedIds.length < 2) {
      setCompare(null)
      return
    }
    const params = selectedIds.map((id) => `ids=${id}`).join('&')
    const res = await fetch(`${API_BASE}/compare?${params}`)
    const data = await res.json()
    setCompare(data)
  }

  useEffect(() => {
    loadFilterOptions()
  }, [])

  useEffect(() => {
    loadFilterOptions()
  }, [sourceFilter])

  useEffect(() => {
    loadProducts()
  }, [bestMode, sourceFilter, productTypeFilter])

  useEffect(() => {
    loadCompare()
  }, [selectedIds])

  // Poll auto-enrichment status every 5 seconds
  useEffect(() => {
    fetchAutoEnrichStatus() // Initial fetch

    const interval = setInterval(() => {
      fetchAutoEnrichStatus()
    }, 5000) // Poll every 5 seconds

    return () => clearInterval(interval)
  }, [])

  const toggleSelect = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const getRecord = (item) => (bestMode ? item.record : item)
  const getNormalized = (item) => (bestMode ? item.normalized : item.normalized_json)

  const parseDateValue = (value) => {
    if (!value) return null
    if (value.includes('-')) {
      const parsed = new Date(value)
      return Number.isNaN(parsed.getTime()) ? null : parsed
    }
    const parts = value.split('.')
    if (parts.length === 3) {
      const [day, month, year] = parts.map((part) => parseInt(part, 10))
      if (!day || !month || !year) return null
      const parsed = new Date(Date.UTC(year, month - 1, day))
      return Number.isNaN(parsed.getTime()) ? null : parsed
    }
    return null
  }

  const getSourceSymbol = (sourceKind) => {
    const symbols = {
      'leonteq_api': '🔷',      // Leonteq API (best quality)
      'leonteq_html': '🔹',     // Leonteq HTML
      'leonteq_html_auth': '🔹', // Leonteq HTML (authenticated)
      'swissquote_html': '🟦',  // Swissquote
      'akb_finanzportal': '🟨', // AKB
      'yahoo_finance': '📊'     // Yahoo Finance
    }
    return symbols[sourceKind] || '❓'
  }

  const getSourceName = (sourceKind) => {
    const names = {
      'leonteq_api': 'Leonteq API',
      'leonteq_html': 'Leonteq',
      'leonteq_html_auth': 'Leonteq',
      'swissquote_html': 'Swissquote',
      'akb_finanzportal': 'AKB',
      'yahoo_finance': 'Yahoo'
    }
    return names[sourceKind] || sourceKind
  }

  const parsePercentValue = (value) => {
    if (value === null || value === undefined) return null
    if (typeof value === 'number') return value
    if (typeof value === 'string') {
      const cleaned = value.replace('%', '').replace(',', '.').trim()
      const parsed = Number(cleaned)
      return Number.isNaN(parsed) ? null : parsed
    }
    return null
  }

  const yearsToMaturity = (normalized) => {
    const maturity = normalized?.maturity_date?.value
    const parsed = parseDateValue(maturity)
    if (!parsed) return null
    const now = new Date()
    const diffMs = parsed.getTime() - now.getTime()
    return diffMs / (1000 * 60 * 60 * 24 * 365)
  }

  const approximateYield = (pricePct, couponPct, redemptionPct, years) => {
    if (!pricePct || !couponPct || !redemptionPct || !years || years <= 0) return null
    const avgPrice = (pricePct + redemptionPct) / 2
    if (avgPrice <= 0) return null
    return ((couponPct + (redemptionPct - pricePct) / years) / avgPrice) * 100
  }

  const getYtmValue = (normalized) => {
    const stored = parsePercentValue(normalized?.yield_to_maturity_pct_pa?.value)
    if (stored !== null) return stored
    const coupon = parsePercentValue(normalized?.coupon_rate_pct_pa?.value)
    const years = yearsToMaturity(normalized)
    if (coupon === null || years === null) return null
    const price = parsePercentValue(normalized?.issue_price_pct?.value) ?? 100
    return approximateYield(price, coupon, 100, years)
  }

  const getWtyValue = (normalized) => {
    const stored = parsePercentValue(normalized?.worst_to_yield_pct_pa?.value)
    if (stored !== null) return stored
    const coupon = parsePercentValue(normalized?.coupon_rate_pct_pa?.value)
    const years = yearsToMaturity(normalized)
    if (coupon === null || years === null) return null
    const price = parsePercentValue(normalized?.issue_price_pct?.value) ?? 100
    const barrier = parsePercentValue(normalized?.underlyings?.[0]?.barrier_pct_of_initial?.value)
    if (barrier === null) return null
    return approximateYield(price, coupon, barrier, years)
  }

  const issuerOptions = useMemo(() => {
    const values = products
      .map((item) => getRecord(item)?.issuer_name || getNormalized(item)?.issuer_name?.value)
      .filter(Boolean)
    return Array.from(new Set(values)).sort()
  }, [products, bestMode])

  const currencyOptions = useMemo(() => {
    const values = products
      .map((item) => getRecord(item)?.currency || getNormalized(item)?.currency?.value)
      .filter(Boolean)
    return Array.from(new Set(values)).sort()
  }, [products, bestMode])

  const ratingOptions = useMemo(() => {
    const values = products
      .map((item) => getNormalized(item)?.issuer_rating?.value)
      .filter(Boolean)
    return Array.from(new Set(values)).sort()
  }, [products, bestMode])

  const filteredProducts = useMemo(() => {
    return products.filter((item) => {
      const record = getRecord(item)
      const normalized = getNormalized(item)
      const issuer = record?.issuer_name || normalized?.issuer_name?.value
      const currency = record?.currency || normalized?.currency?.value
      const rating = normalized?.issuer_rating?.value
      const wtyValue = getWtyValue(normalized)
      const ytmValue = getYtmValue(normalized)

      if (issuerFilter !== 'All' && issuer !== issuerFilter) return false
      if (currencyFilter !== 'All' && currency !== currencyFilter) return false
      if (ratingFilter !== 'All' && rating !== ratingFilter) return false
      if (wtyFilter !== 'All') {
        if (wtyValue === null) return false
        if (wtyFilter === '<2%' && wtyValue >= 2) return false
        if (wtyFilter === '2-5%' && (wtyValue < 2 || wtyValue >= 5)) return false
        if (wtyFilter === '5-8%' && (wtyValue < 5 || wtyValue >= 8)) return false
        if (wtyFilter === '8%+' && wtyValue < 8) return false
      }
      if (ytmFilter !== 'All') {
        if (ytmValue === null) return false
        if (ytmFilter === '<2%' && ytmValue >= 2) return false
        if (ytmFilter === '2-5%' && (ytmValue < 2 || ytmValue >= 5)) return false
        if (ytmFilter === '5-8%' && (ytmValue < 5 || ytmValue >= 8)) return false
        if (ytmFilter === '8%+' && ytmValue < 8) return false
      }
      if (couponFilter !== 'All') {
        const hasCoupon = normalized?.coupon_rate_pct_pa?.value != null
        if (couponFilter === 'Has Coupon' && !hasCoupon) return false
        if (couponFilter === 'Missing Coupon' && hasCoupon) return false
      }
      if (barrierFilter !== 'All') {
        const hasBarrier = (
          normalized?.underlyings?.[0]?.barrier_pct_of_initial?.value != null ||
          normalized?.underlyings?.[0]?.barrier_level?.value != null
        )
        if (barrierFilter === 'Has Barrier' && !hasBarrier) return false
        if (barrierFilter === 'Missing Barrier' && hasBarrier) return false
      }
      if (issueDateFilter !== 'All') {
        const issueDateStr = normalized?.issue_date?.value

        // Handle "Missing Issue Date" filter
        if (issueDateFilter === 'Missing Issue Date') {
          return !issueDateStr
        }

        // For all other filters, require issue date
        if (!issueDateStr) return false

        const issueDate = new Date(issueDateStr)
        const now = new Date()
        const monthsAgo = (now - issueDate) / (1000 * 60 * 60 * 24 * 30)

        if (issueDateFilter === 'Future (Subscription)' && monthsAgo >= 0) return false
        if (issueDateFilter === 'Last 3 months' && (monthsAgo > 3 || monthsAgo < 0)) return false
        if (issueDateFilter === 'Last 6 months' && (monthsAgo > 6 || monthsAgo < 0)) return false
        if (issueDateFilter === 'Last 12 months' && (monthsAgo > 12 || monthsAgo < 0)) return false
        if (issueDateFilter === 'Older than 12 months' && monthsAgo <= 12) return false
      }
      return true
    })
  }, [products, bestMode, issuerFilter, currencyFilter, ratingFilter, wtyFilter, ytmFilter, couponFilter, barrierFilter, issueDateFilter])

  const updateReview = async (id, nextStatus) => {
    await fetch(`${API_BASE}/products/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: nextStatus })
    })
    await loadProducts()
    setStatus(`Updated status to ${nextStatus}`)
  }

  const searchProducts = async (event) => {
    event.preventDefault()
    if (!query.trim()) return
    await fetch(`${API_BASE}/products/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    })
    setQuery('')
    await loadProducts()
    setStatus('Search completed for Leonteq + Swissquote')
  }

  const runCrawl = async () => {
    setCrawlRunning(true)
    setCrawlStatus('Running AKB catalog crawl + enrichment...')
    setCrawlErrors([])
    try {
      const res = await fetch(`${API_BASE}/ingest/crawl/akb-enrich`, { method: 'POST' })
      const data = await res.json()
      setCrawlStatus(`Crawl complete: ${data.ids?.length || 0} records`)
      if (data.errors?.length) {
        setCrawlErrors(data.errors)
      }
      await loadProducts()
    } catch (err) {
      setCrawlStatus('Crawl failed. Check backend logs.')
    } finally {
      setCrawlRunning(false)
    }
  }

  const pollCrawl = (runId, setStatusFn, setErrorsFn, setProgressFn) => {
    const interval = setInterval(async () => {
      const res = await fetch(`${API_BASE}/ingest/crawl/status/${runId}`)
      const data = await res.json()
      if (data.error) {
        setStatusFn('Status not found.')
        clearInterval(interval)
        return
      }
      const total = data.total ?? 0
      const completed = data.completed || 0
      const errors = data.errors_count || 0
      const totalDisplay = data.total === null || data.total === undefined ? '??' : total
      setStatusFn(`Progress ${completed}/${totalDisplay} · errors ${errors}`)
      if (setProgressFn) {
        setProgressFn({ completed, total })
      }
      if (data.last_error) {
        setErrorsFn([data.last_error])
      }
      if (data.status === 'completed') {
        setStatusFn(`✓ Completed: ${completed} products imported`)
        clearInterval(interval)
        await loadProducts()
      } else if (data.status === 'failed') {
        setStatusFn(`✗ Failed: ${data.last_error || 'Unknown error'}`)
        clearInterval(interval)
      }
    }, 2000)
  }

  const runPortalCrawl = async () => {
    setPortalRunning(true)
    setPortalStatus('Running AKB finanzportal catalog...')
    setPortalErrors([])
    try {
      const res = await fetch(`${API_BASE}/ingest/crawl/akb-portal`, { method: 'POST' })
      const data = await res.json()
      pollCrawl(data.run_id, setPortalStatus, setPortalErrors, setPortalProgress)
    } catch (err) {
      setPortalStatus('Catalog failed. Check backend logs.')
    } finally {
      setPortalRunning(false)
    }
  }

  const runScannerCrawl = async () => {
    setScannerRunning(true)
    setScannerStatus('Running Swissquote scanner...')
    setScannerErrors([])
    try {
      const endpoint = sqUser && sqPass ? 'swissquote-scanner-auth' : 'swissquote-scanner'
      const options =
        sqUser && sqPass
          ? {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ username: sqUser, password: sqPass })
            }
          : { method: 'POST' }
      const res = await fetch(`${API_BASE}/ingest/crawl/${endpoint}`, options)
      const data = await res.json()
      pollCrawl(data.run_id, setScannerStatus, setScannerErrors, setScannerProgress)
      setSqPass('')
    } catch (err) {
      setScannerStatus('Scanner failed. Check backend logs.')
    } finally {
      setScannerRunning(false)
    }
  }

  const startSwissquoteLogin = async () => {
    setSqSessionStatus('Opening Swissquote login…')
    try {
      const res = await fetch(`${API_BASE}/ingest/swissquote/login`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'ok') {
        setSqSessionStatus('Swissquote session active')
      } else {
        setSqSessionStatus('Login failed')
      }
    } catch (err) {
      setSqSessionStatus('Login failed')
    }
  }

  const clearSwissquoteSession = async () => {
    await fetch(`${API_BASE}/ingest/swissquote/logout`, { method: 'POST' })
    setSqSessionStatus('Swissquote session cleared')
  }

  const startLeonteqLogin = async () => {
    setLtSessionStatus('Opening Leonteq login…')
    try {
      const res = await fetch(`${API_BASE}/ingest/leonteq/login`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'ok') {
        setLtSessionStatus('Leonteq session active')
      } else {
        setLtSessionStatus('Login failed')
      }
    } catch (err) {
      setLtSessionStatus('Login failed')
    }
  }

  const clearLeonteqSession = async () => {
    await fetch(`${API_BASE}/ingest/leonteq/logout`, { method: 'POST' })
    setLtSessionStatus('Leonteq session cleared')
  }

  const runLeonteqApiCrawl = async () => {
    setLtApiRunning(true)
    setLtApiStatus('Running Leonteq API crawler...')
    try {
      const res = await fetch(`${API_BASE}/ingest/crawl/leonteq-api`, { method: 'POST' })
      const data = await res.json()
      pollCrawl(data.run_id, setLtApiStatus, () => {}, setLtApiProgress)
    } catch (err) {
      setLtApiStatus('API crawl failed. Check backend logs.')
    } finally {
      setLtApiRunning(false)
    }
  }

  const runPdfEnrichment = async () => {
    setEnrichRunning(true)
    setEnrichStatus('Initializing browser and logging in...')
    setEnrichProgress({ enriched: 0, failed: 0, processed: 0 })

    try {
      const res = await fetch(
        `${API_BASE}/enrich/leonteq-pdfs?limit=${enrichLimit}&filter_mode=${enrichFilter}`,
        { method: 'POST' }
      )

      const data = await res.json()

      // Check if API returned an error
      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}: ${res.statusText}`)
      }

      setEnrichProgress({
        enriched: data.enriched || 0,
        failed: data.failed || 0,
        processed: data.processed || 0
      })

      const successRate = data.processed > 0
        ? Math.round((data.enriched / data.processed) * 100)
        : 0

      setEnrichStatus(
        `Complete! Enriched ${data.enriched}/${data.processed} products (${successRate}% success). ` +
        `Failed: ${data.failed}`
      )

      // Reload products to show updated data
      await loadProducts()
    } catch (err) {
      setEnrichStatus(`Failed: ${err.message}`)
      setEnrichProgress({ enriched: 0, failed: 0, processed: 0 })
    } finally {
      setEnrichRunning(false)
    }
  }

  const runFinanzenEnrichment = async () => {
    setFinanzenRunning(true)
    setFinanzenStatus('Initializing browser...')
    setFinanzenProgress({ enriched: 0, failed: 0, processed: 0 })

    try {
      const res = await fetch(
        `${API_BASE}/enrich/finanzen-ch?limit=${finanzenLimit}&filter_mode=${finanzenFilter}`,
        { method: 'POST' }
      )

      const data = await res.json()

      // Check if API returned an error
      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}: ${res.statusText}`)
      }

      setFinanzenProgress({
        enriched: data.enriched || 0,
        failed: data.failed || 0,
        processed: data.processed || 0
      })

      const successRate = data.processed > 0
        ? Math.round((data.enriched / data.processed) * 100)
        : 0

      setFinanzenStatus(
        `Complete! Enriched ${data.enriched}/${data.processed} products (${successRate}% success). ` +
        `Failed: ${data.failed}`
      )

      // Reload products to show updated data
      await loadProducts()
    } catch (err) {
      setFinanzenStatus(`Failed: ${err.message}`)
      setFinanzenProgress({ enriched: 0, failed: 0, processed: 0 })
    } finally {
      setFinanzenRunning(false)
    }
  }

  const startAutoEnrich = async () => {
    try {
      const res = await fetch(
        `${API_BASE}/enrich/auto/start?batch_size=${autoEnrichBatchSize}`,
        { method: 'POST' }
      )
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`)
      }

      setAutoEnrichRunning(true)
      setAutoEnrichStatus(data)
    } catch (err) {
      alert(`Failed to start auto-enrichment: ${err.message}`)
    }
  }

  const stopAutoEnrich = async () => {
    try {
      const res = await fetch(`${API_BASE}/enrich/auto/stop`, { method: 'POST' })
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`)
      }

      setAutoEnrichRunning(false)
      setAutoEnrichStatus(data)
    } catch (err) {
      alert(`Failed to stop auto-enrichment: ${err.message}`)
    }
  }

  const resetAutoEnrich = async () => {
    if (!window.confirm('Reset auto-enrichment to start from the beginning?')) return

    try {
      const res = await fetch(`${API_BASE}/enrich/auto/reset`, { method: 'POST' })
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`)
      }

      setAutoEnrichStatus(null)
      alert(data.message)
    } catch (err) {
      alert(`Failed to reset: ${err.message}`)
    }
  }

  const fetchAutoEnrichStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/enrich/auto/status`)
      const data = await res.json()
      setAutoEnrichStatus(data)
      setAutoEnrichRunning(data.running)
    } catch (err) {
      console.error('Failed to fetch auto-enrich status:', err)
    }
  }

  const clearBackend = async () => {
    if (!window.confirm('Clear all products from the database?')) return
    setClearStatus('Clearing...')
    await fetch(`${API_BASE}/products/clear`, { method: 'POST' })
    await loadProducts()
    setClearStatus('Database cleared')
  }

  const clearIncompleteProducts = async () => {
    const message =
      'This will delete products missing critical fields:\n' +
      '• Products without coupons (for coupon-bearing types)\n' +
      '• Products without barriers (for barrier products)\n' +
      '• Products without underlyings\n\n' +
      'This helps focus on complete, usable data.\n\n' +
      'Continue?'

    if (!window.confirm(message)) return

    setClearStatus('Clearing incomplete products...')
    try {
      const res = await fetch(`${API_BASE}/products/clear-incomplete`, { method: 'POST' })
      const data = await res.json()
      setClearStatus(`Cleared ${data.deleted} incomplete products`)
      await loadProducts()
    } catch (err) {
      setClearStatus('Failed to clear incomplete products')
    }
  }

  const summarizeUnderlyings = (normalized) => {
    if (!normalized?.underlyings?.length) return '—'
    const names = normalized.underlyings
      .map((u) => u?.name?.value)
      .filter(Boolean)
      .slice(0, 3)
    return names.length ? names.map(addSixtMarker).join(', ') : '—'
  }

  const addSixtMarker = (text) => {
    if (!text) return text
    return text.includes('SIXT TCM') ? `${text} *` : text
  }

  const hasTcm = (normalized) => {
    if (!normalized) return false
    const targets = [
      normalized?.product_name?.value,
      ...(normalized?.underlyings || []).map((u) => u?.name?.value)
    ]
    return targets.some((value) => value && value.includes('TCM'))
  }

  const hasPdfData = (normalized) => {
    if (!normalized) return false
    // Check if any field has source='leonteq_pdf'
    const checkSource = (field) => field?.source === 'leonteq_pdf'

    return (
      checkSource(normalized.coupon_rate_pct_pa) ||
      checkSource(normalized.barrier_level_pct) ||
      checkSource(normalized.strike_price) ||
      checkSource(normalized.issue_date) ||
      checkSource(normalized.maturity_date) ||
      checkSource(normalized.denomination) ||
      (normalized.underlyings || []).some(u =>
        checkSource(u.barrier_level_pct) || checkSource(u.strike_price)
      )
    )
  }

  const getBarrier = (normalized) => {
    const first = normalized?.underlyings?.[0]
    return (
      first?.barrier_pct_of_initial?.value ??
      first?.barrier_level?.value ??
      normalized?.barrier_trigger_condition?.value ??
      '—'
    )
  }

  const getBarrierDisplay = (normalized) => {
    const first = normalized?.underlyings?.[0]
    // If we have an absolute barrier level (price), show that
    if (first?.barrier_level?.value) {
      const currency = first?.reference_currency?.value || normalized?.currency?.value || ''
      return `${currency} ${first.barrier_level.value}`
    }
    // Otherwise show percentage
    if (first?.barrier_pct_of_initial?.value) {
      return `${first.barrier_pct_of_initial.value}%`
    }
    // Fallback to other barrier indicators
    if (normalized?.barrier_trigger_condition?.value) {
      return normalized.barrier_trigger_condition.value
    }
    return '—'
  }

  const getFixingDate = (normalized) =>
    normalized?.initial_fixing_date?.value ??
    normalized?.final_fixing_date?.value ??
    '—'

  const getDateTill = (normalized) =>
    normalized?.maturity_date?.value ?? normalized?.redemption_date?.value ?? '—'

  const getMinCapital = (normalized) =>
    normalized?.min_investment?.value ??
    normalized?.denomination?.value ??
    '—'

  const getTradeUnit = (normalized) =>
    normalized?.trade_unit?.value ?? '—'

  const getTermsheetUrl = (item) =>
    bestMode ? item.record?.english_termsheet_url : item.english_termsheet_url

  const getListingVenue = (normalized) =>
    normalized?.listing_venue?.value ?? '—'

  const getCurrencies = (normalized) => {
    const base = normalized?.currency?.value
    const underlyingCurrencies = (normalized?.underlyings || [])
      .map((u) => u?.reference_currency?.value)
      .filter(Boolean)
    const currencies = Array.from(new Set([base, ...underlyingCurrencies].filter(Boolean)))
    return currencies.length ? currencies.join(', ') : '—'
  }

  const getCoupon = (normalized) => normalized?.coupon_rate_pct_pa?.value ?? '—'

  const toggleProfile = (id) => {
    setOpenProfiles((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const profileSummary = (normalized) => {
    const type = (normalized?.product_type?.value || '').toLowerCase()
    const sspa = (normalized?.sspa_category?.value || '').toLowerCase()
    const barrier = getBarrier(normalized)
    const worstOf = normalized?.worst_of?.value
    const capitalProtection = normalized?.capital_protection?.value
    const isReverseConvertible = type.includes('reverse convertible') || sspa.includes('rendite')
    const isCallable = type.includes('callable') || type.includes('autocall') || normalized?.is_callable?.value
    const isMultiBarrierRc =
      isReverseConvertible && (worstOf || type.includes('multi') || type.includes('barrier') || barrier !== '—')
    const isRecovery =
      type.includes('phoenix') ||
      type.includes('recovery') ||
      sspa.includes('phoenix') ||
      sspa.includes('recovery')
    const isTracker = type.includes('tracker') || sspa.includes('tracker')
    const isThematic = type.includes('thematic') || sspa.includes('thematic') || type.includes('basket')
    const isWarrant = type.includes('warrant')
    const isKnockOut =
      type.includes('knock-out') || type.includes('knock out') || type.includes('turbo') || sspa.includes('knock-out')
    const isMiniFuture = type.includes('mini') && type.includes('future')
    const barrierLabel = barrier && barrier !== '—' ? `Barrier ${barrier}` : 'Barrier'

    if (isMultiBarrierRc && isCallable) {
      return {
        title: 'Callable Multi-Barrier Reverse Convertible',
        components: ['Short worst-of down-and-in put', 'Short issuer call'],
        note: 'Sell downside on the worst name and give the issuer the right to call early.',
        triggerLabel: barrierLabel,
        formula: 'Short DI put (worst-of) + short issuer call'
      }
    }
    if (isMultiBarrierRc) {
      return {
        title: 'Multi-Barrier Reverse Convertible',
        components: ['Short worst-of down-and-in put (basket)'],
        note: 'Barrier never hit: option never activates. Barrier hit + W_T < K: linear downside on worst-of.',
        triggerLabel: barrierLabel,
        formula: 'Payoff = 0 if no KI; 0 if KI and W_T >= K; -(K - W_T) if KI and W_T < K'
      }
    }
    if (isReverseConvertible) {
      return {
        title: 'Barrier Reverse Convertible',
        components: ['Short down-and-in put (single underlying)'],
        note: 'Cleaner single-name risk; barrier hit activates short put exposure.',
        triggerLabel: barrierLabel,
        formula: 'Short down-and-in put'
      }
    }
    if (type.includes('autocall') || type.includes('callable')) {
      return {
        title: 'Autocallable',
        components: ['Short autocall trigger feature', 'Short downside optionality'],
        note: 'Issuer can terminate early if triggers are met; upside is capped by design.',
        triggerLabel: barrierLabel
      }
    }
    if (type.includes('bonus') || sspa.includes('bonus')) {
      return {
        title: 'Bonus Certificate',
        components: ['Long underlying', 'Put spread for bonus level', 'Barrier/knock-in'],
        note: 'Bonus if barrier not breached; downside if breached.',
        triggerLabel: `Bonus barrier ${barrier}`
      }
    }
    if (type.includes('capital') || capitalProtection) {
      return {
        title: 'Capital Protected',
        components: ['Zero-coupon bond', 'Long call option'],
        note: 'Downside capped by bond floor; upside via call.',
        triggerLabel: 'Protection floor'
      }
    }
    if (isRecovery) {
      return {
        title: 'Recovery / Phoenix',
        components: ['Short down-and-in put', 'Conditional payoff feature'],
        note: 'You sell tail risk and receive conditional payoffs when the barrier holds.',
        triggerLabel: barrierLabel,
        formula: 'Short DI put + conditional payoff'
      }
    }
    if (isTracker) {
      return {
        title: 'Tracker Certificate',
        components: ['Long spot exposure'],
        note: 'Linear exposure; no optionality.',
        triggerLabel: 'Spot exposure'
      }
    }
    if (isThematic) {
      return {
        title: 'Thematic Certificate',
        components: ['Long rules-based basket'],
        note: 'Basket exposure; rebalancing drives risk.',
        triggerLabel: 'Basket exposure'
      }
    }
    if (isMiniFuture) {
      return {
        title: 'Mini Future',
        components: ['Long leveraged spot', 'Knock-out liquidation barrier'],
        note: 'Linear exposure with forced termination if KO level is breached.',
        triggerLabel: barrierLabel
      }
    }
    if (isKnockOut) {
      return {
        title: 'Knock-Out / Turbo',
        components: ['Long option', 'Hard KO barrier'],
        note: 'Path-dependent termination if barrier touched.',
        triggerLabel: barrierLabel
      }
    }
    if (isWarrant) {
      return {
        title: 'Warrant',
        components: ['Long call or put'],
        note: 'Long convexity; time decay works against you.',
        triggerLabel: 'Option strike'
      }
    }
    if (type.includes('knock-out') || type.includes('warrant') || sspa.includes('hebel')) {
      return {
        title: 'Knock-out / Leverage',
        components: ['Leveraged linear exposure', 'Knock-out barrier'],
        note: 'Position terminates if barrier breached.',
        triggerLabel: barrierLabel
      }
    }

    return {
      title: 'Structured Payoff',
      components: [barrier && barrier !== '—' ? `Barrier ${barrier}` : null, worstOf ? 'Worst-of basket' : null],
      note: 'Generic structured payoff based on available terms.',
      triggerLabel: barrierLabel
    }
  }

  const riskSnapshot = (normalized) => {
    if (!normalized) return []
    const maturity = normalized?.maturity_date?.value
    const barrier = getBarrier(normalized)
    const worstOf = normalized?.worst_of?.value
    const fxRisk = normalized?.fx_risk_flag?.value
    return [
      { label: 'Barrier', value: barrier },
      { label: 'Worst-of', value: worstOf ?? '—' },
      { label: 'FX risk', value: fxRisk ?? '—' },
      { label: 'Maturity', value: maturity ?? '—' }
    ]
  }
  return (
    <div className="app">
      <header className="header">
        <div>
          <p className="eyebrow">Local-first desk</p>
          <h1>Structured Products Analysis</h1>
          <p className="subtitle">Audit-ready normalization with instant comparisons.</p>
          <div className="main-tabs">
            <button
              className={mainTab === 'products' ? 'main-tab active' : 'main-tab'}
              onClick={() => setMainTab('products')}
            >
              Products
            </button>
            <button
              className={mainTab === 'statistics' ? 'main-tab active' : 'main-tab'}
              onClick={() => setMainTab('statistics')}
            >
              Statistics
            </button>
            <button
              className={mainTab === 'settings' ? 'main-tab active' : 'main-tab'}
              onClick={() => setMainTab('settings')}
            >
              Settings
            </button>
          </div>
        </div>
        <form className="isin-form" onSubmit={searchProducts}>
          <label>Search Products</label>
          <div className="isin-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="ISIN, Valor, or Symbol (e.g., CH1505582432, 123456)"
            />
            <button type="submit">Search</button>
          </div>
          {status && <p className="status">{status}</p>}
        </form>
        {/* removed AKB HTML crawl to reduce confusion */}
        <div className="crawl-card">
          <label>Finanzportal catalog</label>
          <button type="button" onClick={runPortalCrawl} disabled={portalRunning}>
            {portalRunning ? 'Crawling…' : 'Run AKB finanzportal catalog'}
          </button>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width:
                  portalProgress.total > 0
                    ? `${Math.min(100, (portalProgress.completed / portalProgress.total) * 100)}%`
                    : '0%'
              }}
            />
          </div>
          {portalStatus && <p className="status">{portalStatus}</p>}
          {portalErrors.length > 0 && (
            <div className="error-list">
              <p>Errors ({portalErrors.length})</p>
              <ul>
                {portalErrors.slice(0, 1).map((err, idx) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="crawl-card">
          <label>Leonteq API Crawler</label>
          <p className="subtitle" style={{fontSize: '13px', marginBottom: '10px', color: '#666'}}>
            <strong>First time?</strong> Click "Open Leonteq login" below → Browse site → Token auto-captured
          </p>
          <div className="session-row" style={{marginBottom: '10px'}}>
            <button type="button" style={{flex: 1}} onClick={startLeonteqLogin}>
              1️⃣ Open Leonteq login (auto-captures token)
            </button>
          </div>
          <button type="button" onClick={runLeonteqApiCrawl} disabled={ltApiRunning}>
            {ltApiRunning ? 'Crawling…' : '2️⃣ Run Leonteq API Crawler'}
          </button>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width:
                  ltApiProgress.total > 0
                    ? `${Math.min(100, (ltApiProgress.completed / ltApiProgress.total) * 100)}%`
                    : '0%'
              }}
            />
          </div>
          {ltApiStatus && <p className="status">{ltApiStatus}</p>}
          <div className="session-row">
            <button type="button" className="toggle" onClick={clearLeonteqSession}>
              Clear session
            </button>
          </div>
          {ltSessionStatus && <p className="status">{ltSessionStatus}</p>}
        </div>
        <div className="crawl-card">
          <label>PDF Enrichment Service</label>
          <p className="subtitle" style={{fontSize: '13px', marginBottom: '10px', color: '#666'}}>
            Extract coupon rates, barriers, and other data from Leonteq termsheet PDFs
          </p>
          <div className="cred-row" style={{marginBottom: '10px', display: 'flex', gap: '10px', alignItems: 'center'}}>
            <label style={{display: 'flex', alignItems: 'center', gap: '8px', flex: 1}}>
              <span style={{minWidth: '80px'}}>Target:</span>
              <select
                value={enrichFilter}
                onChange={(e) => setEnrichFilter(e.target.value)}
                disabled={enrichRunning}
                style={{flex: 1}}
              >
                <option value="missing_any">Missing Coupons OR Barriers</option>
                <option value="missing_coupon">Missing Coupons Only</option>
                <option value="missing_barrier">Missing Barriers Only</option>
                <option value="all">All Leonteq Products</option>
              </select>
            </label>
            <label style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
              <span style={{minWidth: '50px'}}>Limit:</span>
              <input
                type="number"
                min="1"
                max="5000"
                value={enrichLimit}
                onChange={(e) => setEnrichLimit(parseInt(e.target.value) || 100)}
                style={{width: '80px'}}
                disabled={enrichRunning}
              />
            </label>
          </div>
          <button type="button" onClick={runPdfEnrichment} disabled={enrichRunning}>
            {enrichRunning ? 'Enriching…' : '📄 Enrich from PDFs'}
          </button>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width:
                  enrichProgress.processed > 0
                    ? `${Math.min(100, (enrichProgress.processed / enrichLimit) * 100)}%`
                    : '0%'
              }}
            />
          </div>
          {enrichStatus && <p className="status">{enrichStatus}</p>}
          {enrichProgress.processed > 0 && (
            <div style={{marginTop: '10px', fontSize: '13px', color: '#666'}}>
              <div>✅ Enriched: {enrichProgress.enriched}</div>
              <div>❌ Failed: {enrichProgress.failed}</div>
              <div>📊 Processed: {enrichProgress.processed}/{enrichLimit}</div>
            </div>
          )}
          <p className="subtitle" style={{fontSize: '12px', marginTop: '10px', color: '#888'}}>
            Note: Requires prior Leonteq login. PDFs downloaded temporarily and deleted immediately.
          </p>
        </div>
        <div className="crawl-card">
          <label>Finanzen.ch Coupon Crawler</label>
          <p className="subtitle" style={{fontSize: '13px', marginBottom: '10px', color: '#666'}}>
            Extract coupon rates, barriers, and strikes from finanzen.ch product pages
          </p>
          <div className="cred-row" style={{marginBottom: '10px', display: 'flex', gap: '10px', alignItems: 'center'}}>
            <label style={{display: 'flex', alignItems: 'center', gap: '8px', flex: 1}}>
              <span style={{minWidth: '80px'}}>Target:</span>
              <select
                value={finanzenFilter}
                onChange={(e) => setFinanzenFilter(e.target.value)}
                disabled={finanzenRunning}
                style={{flex: 1}}
              >
                <option value="missing_coupon">Missing Coupons Only</option>
                <option value="missing_barrier">Missing Barriers Only</option>
                <option value="missing_any">Missing Coupons OR Barriers</option>
                <option value="all_with_isin">All Products (with ISIN)</option>
              </select>
            </label>
            <label style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
              <span style={{minWidth: '50px'}}>Limit:</span>
              <input
                type="number"
                min="1"
                max="5000"
                value={finanzenLimit}
                onChange={(e) => setFinanzenLimit(parseInt(e.target.value) || 100)}
                style={{width: '80px'}}
                disabled={finanzenRunning}
              />
            </label>
          </div>
          <button type="button" onClick={runFinanzenEnrichment} disabled={finanzenRunning}>
            {finanzenRunning ? 'Crawling…' : '🇨🇭 Crawl Finanzen.ch'}
          </button>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width:
                  finanzenProgress.processed > 0
                    ? `${Math.min(100, (finanzenProgress.processed / finanzenLimit) * 100)}%`
                    : '0%'
              }}
            />
          </div>
          {finanzenStatus && <p className="status">{finanzenStatus}</p>}
          {finanzenProgress.processed > 0 && (
            <div style={{marginTop: '10px', fontSize: '13px', color: '#666'}}>
              <div>✅ Enriched: {finanzenProgress.enriched}</div>
              <div>❌ Failed: {finanzenProgress.failed}</div>
              <div>📊 Processed: {finanzenProgress.processed}/{finanzenLimit}</div>
            </div>
          )}
          <p className="subtitle" style={{fontSize: '12px', marginTop: '10px', color: '#888'}}>
            Note: Works with all products that have ISINs. No login required.
          </p>
        </div>
        <div className="crawl-card">
          <label>Swissquote scanner</label>
          <button type="button" onClick={runScannerCrawl} disabled={scannerRunning}>
            {scannerRunning ? 'Crawling…' : 'Run Swissquote scanner'}
          </button>
          <div className="cred-row">
            <input
              type="text"
              placeholder="Swissquote username"
              value={sqUser}
              onChange={(e) => setSqUser(e.target.value)}
            />
            <input
              type="password"
              placeholder="Swissquote password"
              value={sqPass}
              onChange={(e) => setSqPass(e.target.value)}
            />
          </div>
          <div className="session-row">
            <button type="button" className="toggle" onClick={startSwissquoteLogin}>
              Open Swissquote login
            </button>
            <button type="button" className="toggle" onClick={clearSwissquoteSession}>
              Clear session
            </button>
          </div>
          {sqSessionStatus && <p className="status">{sqSessionStatus}</p>}
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width:
                  scannerProgress.total > 0
                    ? `${Math.min(100, (scannerProgress.completed / scannerProgress.total) * 100)}%`
                    : '0%'
              }}
            />
          </div>
          {scannerStatus && <p className="status">{scannerStatus}</p>}
          {scannerErrors.length > 0 && (
            <div className="error-list">
              <p>Errors ({scannerErrors.length})</p>
              <ul>
                {scannerErrors.slice(0, 1).map((err, idx) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </header>

      {mainTab === 'statistics' ? (
        <Statistics />
      ) : mainTab === 'settings' ? (
        <div className="settings-page">
          <div className="panel" style={{maxWidth: '800px', margin: '0 auto'}}>
            <div className="panel-header">
              <h2>⚙️ Database Settings</h2>
              <span>Manage product data</span>
            </div>

            <div className="settings-section" style={{marginBottom: '30px', padding: '20px', border: '1px solid #3498db', borderRadius: '8px', backgroundColor: '#f0f8ff'}}>
              <h3 style={{marginBottom: '10px', color: '#3498db'}}>🤖 Auto-Enrichment</h3>
              <p style={{marginBottom: '15px', color: '#666', fontSize: '14px'}}>
                Continuously enrich products in the background. Remembers position and resumes automatically.
              </p>

              {autoEnrichStatus && (
                <div style={{marginBottom: '15px', padding: '15px', backgroundColor: '#fff', borderRadius: '4px', border: '1px solid #ddd'}}>
                  <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '13px'}}>
                    <div><strong>Status:</strong> {autoEnrichRunning ? '🟢 Running' : '⚪ Stopped'}</div>
                    <div><strong>Progress:</strong> {autoEnrichStatus.progress_pct}%</div>
                    <div><strong>Enriched:</strong> {autoEnrichStatus.total_enriched}</div>
                    <div><strong>Failed:</strong> {autoEnrichStatus.total_failed}</div>
                    <div><strong>Position:</strong> Offset {autoEnrichStatus.finanzen_offset}</div>
                    <div><strong>Remaining:</strong> ~{autoEnrichStatus.total_missing} products</div>
                  </div>
                </div>
              )}

              <div style={{marginBottom: '15px'}}>
                <label style={{display: 'block', marginBottom: '5px', fontSize: '14px', color: '#666'}}>
                  Batch Size (products per cycle):
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={autoEnrichBatchSize}
                    onChange={(e) => setAutoEnrichBatchSize(parseInt(e.target.value) || 10)}
                    style={{width: '80px', marginLeft: '10px'}}
                    disabled={autoEnrichRunning}
                  />
                </label>
              </div>

              <div style={{display: 'flex', gap: '10px'}}>
                {!autoEnrichRunning ? (
                  <button
                    type="button"
                    onClick={startAutoEnrich}
                    style={{backgroundColor: '#27ae60', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer'}}
                  >
                    ▶️ Start Auto-Enrichment
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={stopAutoEnrich}
                    style={{backgroundColor: '#e74c3c', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer'}}
                  >
                    ⏹️ Stop Auto-Enrichment
                  </button>
                )}
                <button
                  type="button"
                  onClick={resetAutoEnrich}
                  disabled={autoEnrichRunning}
                  style={{backgroundColor: '#95a5a6', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: autoEnrichRunning ? 'not-allowed' : 'pointer', opacity: autoEnrichRunning ? 0.5 : 1}}
                >
                  🔄 Reset Position
                </button>
              </div>

              <p style={{marginTop: '15px', color: '#888', fontSize: '12px', fontStyle: 'italic'}}>
                Note: Processes {autoEnrichBatchSize} products every 30 seconds. Safe to leave running in background.
              </p>
            </div>

            <div className="settings-section" style={{marginBottom: '30px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px'}}>
              <h3 style={{marginBottom: '10px', color: '#e67e22'}}>🧹 Clear Incomplete Products</h3>
              <p style={{marginBottom: '15px', color: '#666', fontSize: '14px'}}>
                Remove products missing critical fields based on their type:
              </p>
              <ul style={{marginBottom: '15px', marginLeft: '20px', color: '#666', fontSize: '14px'}}>
                <li>Barrier products without barrier data</li>
                <li>Coupon products (Reverse Convertibles, Express Certificates) without coupon rates</li>
                <li>Structured products without underlyings</li>
              </ul>
              <p style={{marginBottom: '15px', color: '#888', fontSize: '13px', fontStyle: 'italic'}}>
                This helps focus on complete, usable data and improves data quality metrics.
              </p>
              <button
                type="button"
                onClick={clearIncompleteProducts}
                style={{backgroundColor: '#e67e22', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer'}}
              >
                Clear Incomplete Products
              </button>
            </div>

            <div className="settings-section" style={{marginBottom: '20px', padding: '20px', border: '1px solid #e74c3c', borderRadius: '8px', backgroundColor: '#fff5f5'}}>
              <h3 style={{marginBottom: '10px', color: '#e74c3c'}}>⚠️ Clear All Products</h3>
              <p style={{marginBottom: '15px', color: '#666', fontSize: '14px'}}>
                Delete <strong>all products</strong> from the database. This action cannot be undone.
              </p>
              <p style={{marginBottom: '15px', color: '#c0392b', fontSize: '13px', fontStyle: 'italic'}}>
                Warning: This will permanently delete all product data from all sources. Use only when you need to start fresh.
              </p>
              <button
                type="button"
                onClick={clearBackend}
                style={{backgroundColor: '#e74c3c', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer'}}
              >
                Clear All Products
              </button>
            </div>

            {clearStatus && (
              <p className="status" style={{marginTop: '20px', padding: '10px', backgroundColor: '#ecf0f1', borderRadius: '4px'}}>
                {clearStatus}
              </p>
            )}
          </div>
        </div>
      ) : (
        <main className="main">
          <section className="panel list">
          <div className="panel-header">
            <h2>Products</h2>
            <span>
              {filteredProducts.length} shown
              {serverTotal > 0 && serverTotal !== filteredProducts.length && (
                <> of {serverTotal.toLocaleString()} total</>
              )}
            </span>
          </div>
          <div className="toggle-row">
            <button
              className={bestMode ? 'toggle active' : 'toggle'}
              onClick={() => setBestMode((prev) => !prev)}
            >
              {bestMode ? 'Showing best risk/reward' : 'Show best risk/reward'}
            </button>
          </div>
          <div className="filter-row">
            <label>
              Source
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
                <option>All</option>
                {sourceOptions.map((source) => (
                  <option key={source.value} value={source.value}>
                    {source.label} ({source.count})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Product Type
              <select value={productTypeFilter} onChange={(e) => setProductTypeFilter(e.target.value)}>
                <option>All</option>
                {productTypeOptions.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label} ({type.count})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Issuer
              <select value={issuerFilter} onChange={(e) => setIssuerFilter(e.target.value)}>
                <option>All</option>
                {issuerOptions.map((issuer) => (
                  <option key={issuer} value={issuer}>
                    {issuer}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Currency
              <select value={currencyFilter} onChange={(e) => setCurrencyFilter(e.target.value)}>
                <option>All</option>
                {currencyOptions.map((currency) => (
                  <option key={currency} value={currency}>
                    {currency}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Credit Rating
              <select value={ratingFilter} onChange={(e) => setRatingFilter(e.target.value)}>
                <option>All</option>
                {ratingOptions.map((rating) => (
                  <option key={rating} value={rating}>
                    {rating}
                  </option>
                ))}
              </select>
            </label>
            <label>
              WTY
              <select value={wtyFilter} onChange={(e) => setWtyFilter(e.target.value)}>
                <option>All</option>
                <option>{'<2%'}</option>
                <option>2-5%</option>
                <option>5-8%</option>
                <option>8%+</option>
              </select>
            </label>
            <label>
              YTM
              <select value={ytmFilter} onChange={(e) => setYtmFilter(e.target.value)}>
                <option>All</option>
                <option>{'<2%'}</option>
                <option>2-5%</option>
                <option>5-8%</option>
                <option>8%+</option>
              </select>
            </label>
            <label>
              Coupon
              <select value={couponFilter} onChange={(e) => setCouponFilter(e.target.value)}>
                <option>All</option>
                <option>Has Coupon</option>
                <option>Missing Coupon</option>
              </select>
            </label>
            <label>
              Barrier
              <select value={barrierFilter} onChange={(e) => setBarrierFilter(e.target.value)}>
                <option>All</option>
                <option>Has Barrier</option>
                <option>Missing Barrier</option>
              </select>
            </label>
            <label>
              Issue Date
              <select value={issueDateFilter} onChange={(e) => setIssueDateFilter(e.target.value)}>
                <option>All</option>
                <option>Missing Issue Date</option>
                <option>Future (Subscription)</option>
                <option>Last 3 months</option>
                <option>Last 6 months</option>
                <option>Last 12 months</option>
                <option>Older than 12 months</option>
              </select>
            </label>
          </div>
          <div className="list-grid">
            {filteredProducts.map((product) => (
              <article
                key={bestMode ? product.record.id : product.id}
                className={`card ${
                  selectedSet.has(bestMode ? product.record.id : product.id) ? 'active' : ''
                }`}
              >
                {(() => {
                  const normalized = bestMode ? product.normalized : product.normalized_json
                  const coupon = getCoupon(normalized)
                  return <div className="coupon-badge">{coupon !== '—' ? `${coupon}%` : '—'}</div>
                })()}
                {(() => {
                  const normalized = bestMode ? product.normalized : product.normalized_json
                  return hasTcm(normalized) ? <div className="insured-badge">Insured</div> : null
                })()}
                {(() => {
                  const normalized = bestMode ? product.normalized : product.normalized_json
                  return hasPdfData(normalized) ? <div className="pdf-badge">📄 PDF</div> : null
                })()}
                {(() => {
                  const normalized = bestMode ? product.normalized : product.normalized_json
                  return (
                    <div className="card-metrics">
                      <p>
                        <strong>Underlyings</strong> {summarizeUnderlyings(normalized)}
                      </p>
                      <p>
                        <strong>Barrier</strong> {getBarrier(normalized)}
                      </p>
                      <p>
                        <strong>Fixing</strong> {getFixingDate(normalized)}
                      </p>
                      <p>
                        <strong>Date till</strong> {getDateTill(normalized)}
                      </p>
                      <p>
                        <strong>Min capital</strong> {getMinCapital(normalized)}
                      </p>
                      <p>
                        <strong>Trade unit</strong> {getTradeUnit(normalized)}
                      </p>
                      <p>
                        <strong>Listing</strong> {getListingVenue(normalized)}
                      </p>
                      <p>
                        <strong>Currencies</strong> {getCurrencies(normalized)}
                      </p>
                    </div>
                  )
                })()}
                <div className="card-top">
                  <button
                    className="select"
                    onClick={() => toggleSelect(bestMode ? product.record.id : product.id)}
                  >
                    {selectedSet.has(bestMode ? product.record.id : product.id) ? 'Selected' : 'Select'}
                  </button>
                  <span
                    className={`status-pill status-${
                      bestMode ? product.record.review_status : product.review_status
                    }`}
                  >
                    {bestMode ? product.record.review_status : product.review_status}
                  </span>
                </div>
                <h3>{bestMode ? product.record.isin || product.record.id : product.isin || 'Unknown ISIN'}</h3>
                <p className="meta" style={{fontSize: '12px', opacity: 0.8}}>
                  {(() => {
                    const normalized = bestMode ? product.normalized : product.normalized_json
                    const valor = normalized?.valor_number?.value
                    const id = bestMode ? product.record.id : product.id
                    return (
                      <>
                        {valor && `Valor: ${valor} • `}
                        ID: {id.substring(0, 8)}...
                      </>
                    )
                  })()}
                </p>
                <p className="meta">
                  {getSourceSymbol(bestMode ? product.record.source_kind : product.source_kind)}{' '}
                  {bestMode ? product.record.issuer_name || 'Issuer pending' : product.issuer_name || 'Issuer pending'}
                </p>
                <p className="meta">
                  {(bestMode ? product.record.currency : product.currency) || 'Currency pending'} ·{' '}
                  {(bestMode ? product.record.product_type : product.product_type) || 'Type pending'}
                </p>
                {(() => {
                  const normalized = bestMode ? product.normalized : product.normalized_json
                  const barrierDisplay = getBarrierDisplay(normalized)
                  if (barrierDisplay && barrierDisplay !== '—') {
                    return (
                      <p className="meta" style={{fontSize: '12px', color: '#e67e22'}}>
                        Barrier: {barrierDisplay}
                      </p>
                    )
                  }
                  return null
                })()}
                {bestMode && (
                  <p className="score">Risk/reward score {product.derived.risk_reward_score?.toFixed(3)}</p>
                )}
                <div className="card-actions">
                  <button onClick={() => loadDetail(bestMode ? product.record.id : product.id)}>Detail</button>
                  {(() => {
                    const url = getTermsheetUrl(product)
                    return url ? (
                      <a className="pdf-button" href={url} target="_blank" rel="noreferrer">
                        English PDF
                      </a>
                    ) : (
                      <span className="pdf-button disabled">English PDF</span>
                    )
                  })()}
                  <button
                    onClick={() => toggleProfile(bestMode ? product.record.id : product.id)}
                  >
                    Options profile
                  </button>
                  <button onClick={() => updateReview(bestMode ? product.record.id : product.id, 'reviewed')}>
                    Reviewed
                  </button>
                  <button onClick={() => updateReview(bestMode ? product.record.id : product.id, 'to_be_signed')}>
                    To be signed
                  </button>
                </div>
                {(() => {
                  const normalized = bestMode ? product.normalized : product.normalized_json
                  const productId = bestMode ? product.record.id : product.id
                  if (!openProfiles[productId]) return null
                  const summary = profileSummary(normalized)
                  return (
                    <div className="profile-panel">
                      <div className="profile-diagram">
                        <div className="axis" />
                        <div className="payoff-line" />
                        <div className="barrier-mark">
                          <span>{summary.triggerLabel}</span>
                        </div>
                      </div>
                      <div className="profile-text">
                        <p>
                          <strong>{summary.title}</strong>
                        </p>
                        {summary.components.filter(Boolean).map((item) => (
                          <p key={item}>{item}</p>
                        ))}
                        {summary.formula && (
                          <p className="formula">{summary.formula}</p>
                        )}
                        <p>
                          {summary.note}
                        </p>
                      </div>
                    </div>
                  )
                })()}
              </article>
            ))}
          </div>
        </section>

        <section className="panel detail">
          <div className="panel-header">
            <h2>Detail</h2>
            <span>{detail ? detail.id : 'Select a product'}</span>
          </div>
          <div className="tab-row">
            <button
              className={detailTab === 'detail' ? 'toggle active' : 'toggle'}
              onClick={() => setDetailTab('detail')}
            >
              Detail
            </button>
            <button
              className={detailTab === 'risk' ? 'toggle active' : 'toggle'}
              onClick={() => setDetailTab('risk')}
            >
              Risk/Scenario
            </button>
          </div>
          {detail ? (
            detailTab === 'detail' ? (
              <div className="detail-grid">
                <div>
                  <h3>Identifiers</h3>
                  <p><strong>ISIN</strong> {detail.normalized_json.isin?.value || '—'}</p>
                  <p><strong>Valor</strong> {detail.normalized_json.valor_number?.value || '—'}</p>
                  <p><strong>Issuer</strong> {detail.normalized_json.issuer_name?.value || '—'}</p>
                  <p><strong>Source</strong> {getSourceSymbol(detail.source_kind)} {getSourceName(detail.source_kind)}</p>
                </div>
                <div>
                  <h3>Economics</h3>
                  <p><strong>Currency</strong> {detail.normalized_json.currency?.value || '—'}</p>
                  <p><strong>Coupon</strong> {detail.normalized_json.coupon_rate_pct_pa?.value || '—'}</p>
                  <p><strong>FX risk</strong> {String(detail.normalized_json.fx_risk_flag?.value ?? '—')}</p>
                </div>
                <div>
                  <h3>Options profile</h3>
                  {(() => {
                    const summary = profileSummary(detail.normalized_json)
                    return (
                      <div className="profile-panel">
                        <div className="profile-diagram">
                          <div className="axis" />
                          <div className="payoff-line" />
                          <div className="barrier-mark">
                            <span>{summary.triggerLabel}</span>
                          </div>
                        </div>
                        <div className="profile-text">
                          <p>
                            <strong>{summary.title}</strong>
                          </p>
                          {summary.components.filter(Boolean).map((item) => (
                            <p key={item}>{item}</p>
                          ))}
                          {summary.formula && (
                            <p className="formula">{summary.formula}</p>
                          )}
                          <p>{summary.note}</p>
                        </div>
                      </div>
                    )
                  })()}
                </div>
                <div>
                  <h3>Raw excerpt</h3>
                  <p className="excerpt">{detail.normalized_json.isin?.raw_excerpt || 'No excerpt captured yet.'}</p>
                </div>
              </div>
            ) : (
              <div className="detail-grid">
                <div>
                  <h3>Risk snapshot</h3>
                  {riskSnapshot(detail.normalized_json).map((item) => (
                    <p key={item.label}><strong>{item.label}</strong> {String(item.value)}</p>
                  ))}
                  {detail.derived && (
                    <>
                      <p><strong>Barrier buffer</strong> {detail.derived.barrier_buffer_pct ?? '—'}%</p>
                      <p><strong>Time to maturity</strong> {detail.derived.time_to_maturity_days ?? '—'} days</p>
                      <p><strong>Coupon / vol</strong> {detail.derived.coupon_to_vol_ratio ?? '—'}</p>
                      <p><strong>Vol (1y)</strong> {detail.derived.volatility_annualized ?? '—'}</p>
                      <p><strong>Risk/reward score</strong> {detail.derived.risk_reward_score ?? '—'}</p>
                    </>
                  )}
                </div>
                <div>
                  <h3>Scenario notes</h3>
                  <p className="excerpt">
                    These are heuristic metrics based on available terms and 1y volatility for
                    underlyings. Add payoff math per product type for precise scenario outcomes.
                  </p>
                </div>
              </div>
            )
          ) : (
            <p className="empty">Pick a product to see normalized fields and excerpts.</p>
          )}

          <div className="panel-header compare-header">
            <h2>Compare</h2>
            <span>{selectedIds.length} selected</span>
          </div>
          {compare ? (
            <div className="compare-table">
              {compare.products.map((item) => (
                <div key={item.record.id} className="compare-card">
                  <h4>{item.record.isin || item.record.id}</h4>
                  <p><strong>Maturity</strong> {item.normalized.maturity_date?.value || '—'}</p>
                  <p><strong>Time to maturity</strong> {item.derived.time_to_maturity_days ?? '—'} days</p>
                  <p><strong>Worst of</strong> {String(item.derived.worst_of ?? '—')}</p>
                  <p><strong>FX risk</strong> {String(item.derived.fx_risk_flag ?? '—')}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty">Select at least two products to compare.</p>
          )}
        </section>
        </main>
      )}
    </div>
  )
}

export default App
