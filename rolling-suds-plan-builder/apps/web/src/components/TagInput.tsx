import { useMemo, useState } from 'react';
import type { Tag } from '../types';

type Props = { allTags: Tag[]; selected: Tag[]; onChange: (tags: Tag[]) => void; onCreate: (name: string) => Promise<Tag> };

export function TagInput({ allTags, selected, onChange, onCreate }: Props) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => allTags.filter((t) => t.name.toLowerCase().includes(query.toLowerCase())).slice(0, 8), [allTags, query]);

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
        {selected.map((t) => (
          <button key={t.id} onClick={() => onChange(selected.filter((x) => x.id !== t.id))}>{t.name} ✕</button>
        ))}
      </div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search or create tags" />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
        {filtered.map((t) => (
          <button key={t.id} onClick={() => !selected.find((x) => x.id === t.id) && onChange([...selected, t])}>{t.name}</button>
        ))}
        {query && !filtered.find((f) => f.name.toLowerCase() === query.toLowerCase()) && (
          <button onClick={async () => onChange([...selected, await onCreate(query)])}>Create "{query}"</button>
        )}
      </div>
    </div>
  );
}
