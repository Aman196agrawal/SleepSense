import { analyticsClient } from './client';

export const getSessions   = (limit = 30)        => analyticsClient.get(`/sessions?limit=${limit}`);
export const getSession    = (id: string)         => analyticsClient.get(`/sessions/${id}`);
export const startSession  = ()                   => analyticsClient.post('/sessions');
export const endSession    = (id: string)         => analyticsClient.post(`/sessions/${id}/end`);
export const getTimeline   = (id: string)         => analyticsClient.get(`/analytics/timeline/${id}`);
export const getTrends     = (period = '30d')     => analyticsClient.get(`/analytics/trends?period=${period}`);
export const getWeeklySummary = ()                => analyticsClient.get('/analytics/weekly-summary');
export const getInsights     = ()                  => analyticsClient.get('/insights');
export const markInsightRead = (id: string)        => analyticsClient.patch(`/insights/${id}/read`);

export const uploadChunk = (
  sessionId: string,
  data: { chunk_index: number; avg_intensity: number; dominant_class: string; snore_event_count: number }
) => analyticsClient.post(`/sessions/${sessionId}/chunks`, data);

export const logLifestyle    = (data: {
  logged_date: string;
  caffeine_cups: number;
  alcohol_units: number;
  exercise_minutes: number;
  stress_level: number;
  sleep_aid_used: boolean;
}) => analyticsClient.post('/lifestyle', data);
export const getLifestyleLogs        = (days = 14) => analyticsClient.get(`/lifestyle?days=${days}`);
export const getLifestyleCorrelations = ()         => analyticsClient.get('/lifestyle/correlations');
