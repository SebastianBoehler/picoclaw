import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import DataView from './pages/DataView'
import JobsPage from './pages/JobsPage'
import './App.css'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/data" element={<DataView />} />
          <Route path="/jobs" element={<JobsPage />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
