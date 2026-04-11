import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { WorkizAppointment } from '../types';

export function ImportWorkizPage({ userId, onImported }: { userId: string; onImported: (assessmentId: string) => void }) {
  const [rows, setRows] = useState<WorkizAppointment[]>([]);
  const [q, setQ] = useState('');

  useEffect(() => { api.workizAppointments(q).then(setRows); }, [q]);

  return (
    <section>
      <h2>Import from Workiz</h2>
      <input placeholder="Search customer, address, phone, record" value={q} onChange={(e) => setQ(e.target.value)} />
      <div>
        {rows.map((r) => (
          <article key={r.appointmentId} style={{ border: '1px solid #ddd', marginTop: 10, padding: 10 }}>
            <strong>{r.customerName}</strong>
            <div>{r.address}</div>
            <div>{new Date(r.scheduledStart).toLocaleString()} • {r.status}</div>
            <button onClick={async () => {
              const imported = await api.importWorkiz(r.appointmentId, userId);
              onImported(imported.assessment.id);
            }}>Import into assessment draft</button>
          </article>
        ))}
      </div>
    </section>
  );
}
