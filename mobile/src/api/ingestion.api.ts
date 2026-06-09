import { ingestionClient } from './client';

export const startSession = () => ingestionClient.post('/sessions');

export const endSession = (sessionId: string, opts?: {
  ended_at?: string;
  notes?: string;
  room_temperature?: number;
}) => ingestionClient.post(`/sessions/${sessionId}/end`, opts ?? {});

/**
 * Upload a 30-second audio chunk (binary multipart) to the ingestion service.
 * `audioUri` is a local file URI produced by expo-audio after stopping a recording.
 */
export const uploadBinaryChunk = (
  sessionId: string,
  audioUri: string,
  chunkIndex: number,
  durationSeconds: number,
): Promise<any> => {
  const formData = new FormData();
  formData.append('audio', {
    uri: audioUri,
    name: `chunk_${String(chunkIndex).padStart(3, '0')}.m4a`,
    type: 'audio/m4a',
  } as any);
  formData.append('chunk_index', String(chunkIndex));
  formData.append('duration_seconds', String(durationSeconds));
  return ingestionClient.post(`/sessions/${sessionId}/chunks`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  });
};

export const getStatus = (sessionId: string) =>
  ingestionClient.get(`/sessions/${sessionId}/status`);

export const deleteAudio = (sessionId: string) =>
  ingestionClient.delete(`/sessions/${sessionId}/audio`);
