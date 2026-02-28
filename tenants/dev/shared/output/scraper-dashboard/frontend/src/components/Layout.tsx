import { Link, useLocation } from 'react-router-dom'
import './Layout.css'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/data', label: 'Data', icon: '📋' },
    { path: '/jobs', label: 'Jobs', icon: '⚙️' },
  ]

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">
          <h2>🔍 Scraper</h2>
        </div>
        <nav className="nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">
        {children}
      </main>
    </div>
  )
}
