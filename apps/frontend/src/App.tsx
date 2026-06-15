import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { isLoggedIn } from './lib/auth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import EventListPage from './pages/EventListPage'
import EventDetailPage from './pages/EventDetailPage'
import ReviewQueuePage from './pages/ReviewQueuePage'
import StatsPage from './pages/StatsPage'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  return isLoggedIn() ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route path="/" element={<DashboardPage />} />
          <Route path="/events" element={<EventListPage />} />
          <Route path="/events/:id" element={<EventDetailPage />} />
          <Route path="/review-queue" element={<ReviewQueuePage />} />
          <Route path="/review-queue/:queue_id" element={<ReviewQueuePage />} />
          <Route path="/stats" element={<StatsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
