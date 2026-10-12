import { DashboardLayout } from './components/DashboardLayout';
import { ReviewsTable } from './components/ReviewsTable';
import { AnalysisPanel } from './components/AnalysisPanel';
import { useAppStore } from './store/useAppStore';

/**
 * Главный компонент приложения
 * B2B Dashboard с утилитарным flat-design + Zustand + shadcn/ui
 */
function App() {
  const { user, logout } = useAppStore();

  return (
    <DashboardLayout
      title="Аналитика"
      userEmail={user?.email}
      quota={null}
      online={true}
      onLogout={logout}
    >
      {/* CONTENT AREA */}
      <div className="space-y-6">
        {/* Analytics Panel */}
        <AnalysisPanel />

        {/* Reviews Table */}
        <ReviewsTable />
      </div>
    </DashboardLayout>
  );
}

export default App;
