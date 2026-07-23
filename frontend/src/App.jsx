import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './contexts/AppContext';
import { ToastProvider } from './contexts/ToastContext';
import Layout from './components/layout/Layout';
import OverviewPage from './pages/overview/OverviewPage';
import SyncPage from './pages/sync/SyncPage';
import HistoryPage from './pages/history/HistoryPage';
import HistoryDetail from './pages/history/HistoryDetail';
import StatsPage from './pages/stats/StatsPage';
import FormsPage from './pages/forms/FormsPage';
import SettingsPage from './pages/settings/SettingsPage';
import DiagnosticsPage from './pages/diagnostics/DiagnosticsPage';

function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <ToastProvider>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/overview" replace />} />
              <Route path="overview" element={<OverviewPage />} />
              <Route path="sync" element={<SyncPage />} />
              <Route path="history">
                <Route index element={<HistoryPage />} />
                <Route path=":runId" element={<HistoryDetail />} />
              </Route>
              <Route path="stats" element={<StatsPage />} />
              <Route path="forms" element={<FormsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="diagnostics" element={<DiagnosticsPage />} />
            </Route>
          </Routes>
        </ToastProvider>
      </AppProvider>
    </BrowserRouter>
  );
}

export default App;
