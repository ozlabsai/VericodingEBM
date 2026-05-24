import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import LandscapePage from './LandscapePage'
import LandscapePage3D from './LandscapePage3D'
import './index.css'

const path = window.location.pathname
const Component =
  path === '/landscape3d' ? LandscapePage3D :
  path === '/landscape'   ? LandscapePage   :
  App

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Component />
  </React.StrictMode>,
)
