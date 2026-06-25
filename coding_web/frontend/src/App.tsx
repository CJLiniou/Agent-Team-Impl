import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import TaskDetailPage from './pages/TaskDetailPage';
import TeamEditorPage from './pages/TeamEditorPage';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
        <Route path="/teams" element={<TeamEditorPage />} />
      </Routes>
    </div>
  );
}
