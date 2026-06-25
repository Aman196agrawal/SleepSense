import { ingestionClient } from './client';

export const startSession = () => ingestionClient.post('/sessions');

export const endSession = (sessionId: string, opts?: {
  ended_at?: string;
  notes?: string;
  room_temperature?: number;
}) => ingestionClient.post(`/sessions/${sessionId}/end`, opts ?? {});

/**
 * Upload a 30-second audio chunk (binary multipart) to the ingestion service.
 * `audioUri` is a local WAV file URI assembled in JS from the continuous PCM
 * stream (see RecordScreen flushChunk).
 */
export const uploadBinaryChunk = (
  sessionId: string,
  audioUri: string,
  chunkIndex: number,
  durationSeconds: number,
  uploadToken?: string | null,
): Promise<any> => {
  const formData = new FormData();
  formData.append('audio', {
    uri: audioUri,
    name: `chunk_${String(chunkIndex).padStart(3, '0')}.wav`,
    type: 'audio/wav',
  } as any);
  formData.append('chunk_index', String(chunkIndex));
  formData.append('duration_seconds', String(durationSeconds));
  const headers: Record<string, string> = { 'Content-Type': 'multipart/form-data' };
  // Capability token (from analytics startSession) proving this user owns the
  // session — required by ingestion to create a session it didn't itself start.
  if (uploadToken) headers['X-Upload-Token'] = uploadToken;
  return ingestionClient.post(`/sessions/${sessionId}/chunks`, formData, {
    headers,
    timeout: 60000,
  });
};

export const getStatus = (sessionId: string) =>
  ingestionClient.get(`/sessions/${sessionId}/status`);

export const deleteAudio = (sessionId: string) =>
  ingestionClient.delete(`/sessions/${sessionId}/audio`);
