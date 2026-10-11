import { DashboardLayout } from './components/DashboardLayout'
import { ReviewsTable } from './components/ReviewsTable'
import { AnalysisPanel } from './components/AnalysisPanel'

/**
 * Главный компонент приложения
 * B2B Dashboard с утилитарным flat-design + Zustand + shadcn/ui
 */
function App() {
  return (
    <DashboardLayout>
      {/* CONTENT AREA */}
      <div className="p-6 space-y-6">
        {/* Analytics Panel */}
        <AnalysisPanel />

        {/* Reviews Table */}
        <ReviewsTable />
      </div>
    </DashboardLayout>
  )
}

export default App
