import type { ReactNode } from 'react'
import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './pages/LoginPage'
import { DashboardHomePage } from './pages/DashboardHomePage'
import { ProjectsListPage } from './pages/ProjectsListPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { NewDubbingProjectPage } from './pages/NewDubbingProjectPage'
import { NewSubtitlesProjectPage } from './pages/NewSubtitlesProjectPage'
import { NewTranscriptionProjectPage } from './pages/NewTranscriptionProjectPage'
import { NewTtsProjectPage } from './pages/NewTtsProjectPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function ProtectedPage({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedPage>
                  <DashboardHomePage />
                </ProtectedPage>
              }
            />
            <Route
              path="/dubbing/new"
              element={
                <ProtectedPage>
                  <NewDubbingProjectPage />
                </ProtectedPage>
              }
            />
            <Route
              path="/subtitles/new"
              element={
                <ProtectedPage>
                  <NewSubtitlesProjectPage />
                </ProtectedPage>
              }
            />
            <Route
              path="/transcription/new"
              element={
                <ProtectedPage>
                  <NewTranscriptionProjectPage />
                </ProtectedPage>
              }
            />
            <Route
              path="/tts/new"
              element={
                <ProtectedPage>
                  <NewTtsProjectPage />
                </ProtectedPage>
              }
            />
            <Route
              path="/projects"
              element={
                <ProtectedPage>
                  <ProjectsListPage />
                </ProtectedPage>
              }
            />
            <Route
              path="/projects/:id"
              element={
                <ProtectedPage>
                  <ProjectDetailPage />
                </ProtectedPage>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
