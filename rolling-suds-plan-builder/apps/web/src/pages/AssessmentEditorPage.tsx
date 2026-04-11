import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { TagInput } from '../components/TagInput';
import type { Tag } from '../types';

export function AssessmentEditorPage({ assessmentId }: { assessmentId: string }) {
  const [record, setRecord] = useState<any>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [saveState, setSaveState] = useState('Saved');

  useEffect(() => {
    api.assessment(assessmentId).then(setRecord);
    api.tags().then(setTags);
  }, [assessmentId]);

  const quickButtons = useMemo(() => ['Siding', 'Gutter', 'Patio'], []);

  if (!record) return <p>Loading assessment...</p>;

  return (
    <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
      <div>
        <h2>Assessment Editor</h2>
        <p>{saveState}</p>
        <textarea
          style={{ width: '100%', minHeight: 110 }}
          value={record.overallSummary ?? ''}
          onChange={(e) => setRecord({ ...record, overallSummary: e.target.value })}
          onBlur={async () => {
            setSaveState('Saving...');
            await api.updateAssessment(assessmentId, { overallSummary: record.overallSummary });
            setSaveState('Saved');
          }}
          placeholder="Dictate or type overall summary"
        />

        <div style={{ display: 'flex', gap: 8, margin: '12px 0' }}>
          {quickButtons.map((label) => (
            <button key={label} onClick={() => setRecord({ ...record, observations: [...record.observations, { surfaceType: label, notes: '', tagIds: [] }] })}>Add {label} observation</button>
          ))}
        </div>

        {record.observations.map((obs: any, i: number) => (
          <div key={obs.id ?? i} style={{ border: '1px solid #ddd', padding: 12, marginBottom: 12 }}>
            <input value={obs.surfaceType ?? ''} onChange={(e) => {
              const observations = [...record.observations];
              observations[i].surfaceType = e.target.value;
              setRecord({ ...record, observations });
            }} placeholder="Surface type" />
            <textarea style={{ width: '100%', minHeight: 80 }} value={obs.conditionObserved ?? ''} onChange={(e) => {
              const observations = [...record.observations];
              observations[i].conditionObserved = e.target.value;
              setRecord({ ...record, observations });
            }} placeholder="Condition observed (dictation friendly)" />
            <textarea style={{ width: '100%', minHeight: 80 }} value={obs.notes ?? ''} onChange={(e) => {
              const observations = [...record.observations];
              observations[i].notes = e.target.value;
              setRecord({ ...record, observations });
            }} placeholder="Special notes (typed/dictated)" />
            <TagInput
              allTags={tags}
              selected={(obs.tags ?? []).map((t: any) => t.tag ?? t)}
              onChange={(selectedTags) => {
                const observations = [...record.observations];
                observations[i].tags = selectedTags;
                setRecord({ ...record, observations });
              }}
              onCreate={async (name) => {
                const tag = await api.createTag({ name, category: 'custom' });
                setTags((prev) => [...prev, tag]);
                return tag;
              }}
            />
            <button onClick={async () => {
              setSaveState('Saving...');
              await api.upsertObservation({ ...obs, assessmentId, tagIds: (obs.tags ?? []).map((t: any) => t.id || t.tagId), inputMode: 'mixed', sortOrder: i });
              setSaveState('Saved');
            }}>Save observation</button>
          </div>
        ))}
      </div>

      <aside style={{ background: '#fafafa', padding: 16 }}>
        <h3>Live Client Preview</h3>
        <h4>{record.title}</h4>
        <p>{record.customer.firstName} {record.customer.lastName}</p>
        <p>{record.property.serviceAddress}, {record.property.city}</p>
        <p>{record.overallSummary}</p>
        {record.observations.map((obs: any, i: number) => (
          <div key={i}><strong>{obs.surfaceType}</strong><p>{obs.conditionObserved || obs.notes}</p></div>
        ))}
        <a href={`${import.meta.env.VITE_API_URL ?? 'http://localhost:4000/api'}/assessments/${assessmentId}/pdf`} target="_blank">Export PDF</a>
      </aside>
    </section>
  );
}
