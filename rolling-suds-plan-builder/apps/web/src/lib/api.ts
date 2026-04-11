const API = import.meta.env.VITE_API_URL ?? 'http://localhost:4000/api';

let token = localStorage.getItem('token') ?? '';
export const setToken = (t: string) => {
  token = t;
  localStorage.setItem('token', t);
};

async function request(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  login: (email: string, password: string) => request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  workizAppointments: (q = '') => request(`/workiz/appointments?q=${encodeURIComponent(q)}`),
  importWorkiz: (id: string, userId: string) => request(`/workiz/appointments/${id}/import`, { method: 'POST', body: JSON.stringify({ userId }) }),
  assessment: (id: string) => request(`/assessments/${id}`),
  updateAssessment: (id: string, payload: unknown) => request(`/assessments/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  upsertObservation: (payload: unknown) => request('/assessments/observation', { method: 'POST', body: JSON.stringify(payload) }),
  tags: (q = '') => request(`/tags?q=${encodeURIComponent(q)}`),
  createTag: (payload: unknown) => request('/tags', { method: 'POST', body: JSON.stringify(payload) })
};
