/**
 * Turns anything thrown by an API call into a string safe to render.
 *
 * FastAPI returns `detail` as a plain string for `HTTPException`, but as an
 * ARRAY of `{type, loc, msg, input, ctx}` objects for 422 validation failures.
 * Assigning that array straight into state and rendering it crashes the screen
 * with "Objects are not valid as a React child", so every call site must go
 * through here rather than reading `response.data.detail` directly.
 */

/** Pydantic prefixes custom `ValueError`s with "Value error, " — drop it. */
const clean = (m: string) => m.replace(/^value error,\s*/i, '').trim();

type FastApiError = { msg?: unknown; loc?: unknown };

export function apiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  const e = err as any;
  const res = e?.response;

  // A request went out but nothing came back: offline, wrong host, or timeout.
  if (!res) {
    if (e?.code === 'ECONNABORTED') return 'The server took too long to respond. Please try again.';
    if (e?.request) return 'Cannot reach the server. Check your connection and try again.';
    return fallback;
  }

  const detail = res?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) return clean(detail);

  // 422 validation: collect each field's message, de-duplicated, one per line.
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d: FastApiError) => (typeof d?.msg === 'string' ? clean(d.msg) : ''))
      .filter(Boolean);
    if (msgs.length) return Array.from(new Set(msgs)).join('\n');
  }

  if (detail && typeof detail === 'object') {
    const msg = (detail as FastApiError).msg;
    if (typeof msg === 'string' && msg.trim()) return clean(msg);
  }

  if (typeof res?.data?.message === 'string' && res.data.message.trim()) {
    return res.data.message.trim();
  }

  return fallback;
}
