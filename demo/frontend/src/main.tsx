import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import LandscapePage from './LandscapePage'
import LandscapePage3D from './LandscapePage3D'
import LandingPage from './LandingPage'
import './index.css'

// Strip a deploy-time base prefix (e.g. `/VericodingEBM/`) before matching
// route paths, so the same router works at the root of HF Spaces and under a
// GitHub Pages project-page subpath.
function currentRoute(): string {
  const base = (import.meta as any).env?.BASE_URL ?? '/'
  let p = window.location.pathname
  if (base !== '/' && p.startsWith(base)) p = p.slice(base.length - 1)  // keep leading /
  // Normalize trailing slash
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1)
  return p
}

const path = currentRoute()
const Component =
  path === '/landscape3d' ? LandscapePage3D :
  path === '/landscape'   ? LandscapePage   :
  path === '/manifold'    ? App             :
  path === '/' || path === ''
                          ? LandingPage     :
  LandingPage  // fallback: unknown route shows landing

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Component />
  </React.StrictMode>,
)
