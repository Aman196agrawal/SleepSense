/**
 * Durable-ish retry queue for audio chunk uploads.
 *
 * Chunks used to be uploaded fire-and-forget: a single failed request dropped
 * that chunk for good, and the temp WAV was deleted in `.finally()` either way,
 * so there was nothing left to retry with. On a phone on home Wi-Fi across an
 * eight-hour night that is not an edge case.
 *
 * Here the queue owns the file: it is deleted only once the upload has either
 * succeeded or definitively failed. Uploads run one at a time so a backlog
 * cannot stampede the server, with exponential backoff between attempts.
 *
 * Not persisted across app restarts — the temp files live in the cache
 * directory, which the OS may reclaim anyway. This survives network blips,
 * which is what actually loses data in practice.
 */
import * as FileSystem from 'expo-file-system/legacy';
import * as IngestionAPI from './ingestion.api';

export type QueueStats = {
  /** Waiting or mid-retry. */
  pending: number;
  /** Uploaded successfully this session. */
  uploaded: number;
  /** Given up on — retries exhausted, rejected outright, or evicted. */
  failed: number;
};

type Job = {
  sessionId: string;
  uri: string;
  index: number;
  durationSec: number;
  token: string | null;
  attempts: number;
  readyAt: number;
};

const MAX_ATTEMPTS = 5;
const BACKOFF_MS = [2000, 5000, 12000, 30000, 60000];
/** ~200 chunks ≈ 100 min of audio held back. Beyond this the oldest is dropped
 *  so a long outage cannot fill the device's storage. */
const MAX_QUEUE = 200;

let queue: Job[] = [];
let running = false;
let stats: QueueStats = { pending: 0, uploaded: 0, failed: 0 };
let listener: ((s: QueueStats) => void) | null = null;

function emit() {
  stats = { ...stats, pending: queue.length };
  listener?.(stats);
}

async function removeFile(uri: string) {
  try {
    await FileSystem.deleteAsync(uri, { idempotent: true });
  } catch {
    // Cache file — losing the delete is not worth surfacing.
  }
}

/**
 * Should this failure be retried?
 *
 * A 409 means the server already has that index, so the job is done. Other 4xx
 * responses (401, 413, 422, …) describe something about the request that will
 * not change by sending it again — retrying those just burns battery. Network
 * errors and 5xx are the ones worth repeating.
 */
function classify(err: any): 'done' | 'retry' | 'permanent' {
  const status = err?.response?.status;
  if (status === 409) return 'done';
  if (status === undefined) return 'retry';          // no response: offline/timeout
  if (status === 408 || status === 429) return 'retry';
  if (status >= 500) return 'retry';
  return 'permanent';
}

async function pump() {
  if (running) return;
  running = true;
  try {
    while (queue.length) {
      const job = queue[0];
      const wait = job.readyAt - Date.now();
      if (wait > 0) await new Promise(r => setTimeout(r, Math.min(wait, 5000)));
      if (Date.now() < job.readyAt) continue;        // still backing off

      try {
        await IngestionAPI.uploadBinaryChunk(
          job.sessionId, job.uri, job.index, job.durationSec, job.token);
        queue.shift();
        stats.uploaded += 1;
        await removeFile(job.uri);
      } catch (err: any) {
        const verdict = classify(err);
        if (verdict === 'done') {
          queue.shift();
          stats.uploaded += 1;
          await removeFile(job.uri);
        } else if (verdict === 'permanent' || job.attempts + 1 >= MAX_ATTEMPTS) {
          queue.shift();
          stats.failed += 1;
          console.warn(
            `[uploadQueue] giving up on chunk ${job.index} after ${job.attempts + 1} ` +
            `attempt(s): ${err?.response?.status ?? err?.message ?? 'unknown'}`);
          await removeFile(job.uri);
        } else {
          job.attempts += 1;
          job.readyAt = Date.now() + BACKOFF_MS[Math.min(job.attempts - 1, BACKOFF_MS.length - 1)];
          // Move to the back so one stuck chunk cannot block newer ones. The
          // server accepts gaps and out-of-order indices, so this is safe.
          queue.push(queue.shift()!);
        }
      }
      emit();
    }
  } finally {
    running = false;
  }
}

export const uploadQueue = {
  enqueue(job: Omit<Job, 'attempts' | 'readyAt'>) {
    if (queue.length >= MAX_QUEUE) {
      const dropped = queue.shift();
      if (dropped) {
        stats.failed += 1;
        console.warn(`[uploadQueue] queue full, dropping chunk ${dropped.index}`);
        void removeFile(dropped.uri);
      }
    }
    queue.push({ ...job, attempts: 0, readyAt: 0 });
    emit();
    void pump();
  },

  /** Wait for the backlog to drain, up to `timeoutMs`. Used when a session ends. */
  async drain(timeoutMs = 20000): Promise<QueueStats> {
    const deadline = Date.now() + timeoutMs;
    void pump();
    while (queue.length && Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 400));
    }
    return { ...stats, pending: queue.length };
  },

  /** Drop everything and delete the held files (session discarded). */
  async clear() {
    const held = queue;
    queue = [];
    emit();
    await Promise.all(held.map(j => removeFile(j.uri)));
  },

  reset() {
    stats = { pending: queue.length, uploaded: 0, failed: 0 };
    emit();
  },

  getStats(): QueueStats {
    return { ...stats, pending: queue.length };
  },

  onChange(fn: ((s: QueueStats) => void) | null) {
    listener = fn;
  },
};
