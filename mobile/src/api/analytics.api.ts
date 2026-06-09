import { analyticsClient } from './client';

export const getSessions = (limit = 20, cursor?: string) => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set('cursor', cursor);
  return analyticsClient.get(`/sessions?${params}`);
};
export const getSession       = (id: string)  => analyticsClient.get(`/sessions/${id}`);
export const getSessionStatus = (id: string)  => analyticsClient.get(`/sessions/${id}/status`);
export const startSession     = ()            => analyticsClient.post('/sessions');
export const endSession       = (id: string)  => analyticsClient.post(`/sessions/${id}/end`);
export const deleteSessionAudio = (id: string) => analyticsClient.delete(`/sessions/${id}/audio`);

export const exportCSV = (from?: string, to?: string) => {
  const params = new URLSearchParams();
  if (from) params.set('from_date', from);
  if (to)   params.set('to_date', to);
  return analyticsClient.get(`/sessions/export?${params}`);
};

export const getTimeline      = (id: string)  => analyticsClient.get(`/analytics/timeline/${id}`);
export const getTrends        = (period = '30d') => analyticsClient.get(`/analytics/trends?period=${period}`);
export const getWeeklySummary = ()            => analyticsClient.get('/analytics/weekly-summary');
export const getStreak        = ()            => analyticsClient.get('/analytics/streak');

export const getInsights      = ()            => analyticsClient.get('/insights');
export const markInsightRead  = (id: string)  => analyticsClient.patch(`/insights/${id}/read`);

export const uploadChunk = (
  sessionId: string,
  data: { chunk_index: number; avg_intensity: number; dominant_class: string; snore_event_count: number }
) => analyticsClient.post(`/sessions/${sessionId}/chunks`, data);

export const logLifestyle = (data: {
  logged_date: string;
  caffeine_cups: number;
  alcohol_units: number;
  exercise_minutes: number;
  stress_level: number;
  sleep_aid_used: boolean;
}) => analyticsClient.post('/lifestyle', data);

export const getLifestyleLogs        = (days = 14) => analyticsClient.get(`/lifestyle?days=${days}`);
export const getLifestyleCorrelations = ()          => analyticsClient.get('/lifestyle/correlations');

export const getGoals    = ()            => analyticsClient.get('/goals');
export const createGoal  = (data: { goal_type: string; target_value: number; target_date?: string }) =>
  analyticsClient.post('/goals', data);
export const deleteGoal  = (id: string)  => analyticsClient.delete(`/goals/${id}`);

export const getCalendar      = (days = 90) => analyticsClient.get(`/analytics/calendar?days=${days}`);
export const getScoreBreakdown = (id: string) => analyticsClient.get(`/sessions/${id}/score-breakdown`);
export const getAudioUrl       = (sessionId: string, chunkIndex: number) =>
  analyticsClient.get(`/sessions/${sessionId}/audio-url/${chunkIndex}`);
