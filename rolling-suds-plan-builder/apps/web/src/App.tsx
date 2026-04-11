import { useState } from 'react';
import { LoginPage } from './pages/LoginPage';
import { ImportWorkizPage } from './pages/ImportWorkizPage';
import { AssessmentEditorPage } from './pages/AssessmentEditorPage';

export default function App() {
  const [user, setUser] = useState<{ id: string; name: string } | null>(null);
  const [assessmentId, setAssessmentId] = useState<string | null>(null);

  if (!user) return <LoginPage onDone={setUser} />;

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: 20, fontFamily: 'Inter, sans-serif' }}>
      <h1>Rolling Suds Property Cleaning Plan Builder</h1>
      {!assessmentId ? <ImportWorkizPage userId={user.id} onImported={setAssessmentId} /> : <AssessmentEditorPage assessmentId={assessmentId} />}
    </main>
  );
}
