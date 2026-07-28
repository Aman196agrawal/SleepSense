/**
 * Client-side mirror of the auth service's password policy.
 *
 * Keep in sync with `_validate_password_strength` in
 * `services/auth-service/app/schemas.py`. If these drift, the user passes
 * client validation and then gets a 422 from the server instead — which is
 * exactly the failure this module exists to prevent.
 */

/** Same character set the server accepts as "special". */
const SPECIAL_RE = /[!@#$%^&*()\-_=+[\]{};:'",.<>?/\\|`~]/;

/** bcrypt truncates past 72 bytes, so the server rejects longer secrets. */
export const MAX_PASSWORD_BYTES = 72;

export type PasswordRule = { key: string; label: string; test: (v: string) => boolean };

export const PASSWORD_RULES: PasswordRule[] = [
  { key: 'length',  label: 'At least 8 characters', test: v => v.length >= 8 },
  { key: 'upper',   label: 'One uppercase letter',  test: v => /[A-Z]/.test(v) },
  { key: 'number',  label: 'One number',            test: v => /\d/.test(v) },
  { key: 'special', label: 'One special character', test: v => SPECIAL_RE.test(v) },
];

/** UTF-8 byte length without relying on TextEncoder being present in Hermes. */
export function utf8ByteLength(s: string): number {
  let n = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s.codePointAt(i)!;
    if (c < 0x80) n += 1;
    else if (c < 0x800) n += 2;
    else if (c < 0x10000) n += 3;
    else { n += 4; i++; } // surrogate pair consumed
  }
  return n;
}

/** Rules the password does NOT yet satisfy, in display order. */
export function unmetRules(v: string): PasswordRule[] {
  return PASSWORD_RULES.filter(r => !r.test(v));
}

/**
 * Returns a user-facing error, or null when the password would be accepted.
 * Phrased to match the server's own wording so the two never contradict.
 */
export function validatePassword(v: string): string | null {
  if (!v) return 'Password is required';
  if (utf8ByteLength(v) > MAX_PASSWORD_BYTES) {
    return `Password must be at most ${MAX_PASSWORD_BYTES} bytes long`;
  }
  const missing = unmetRules(v);
  if (missing.length) {
    return `Password must contain: ${missing.map(r => r.label.toLowerCase()).join(', ')}`;
  }
  return null;
}

/** 0-4, one point per satisfied rule — drives the strength meter. */
export function passwordStrength(v: string): { level: 0 | 1 | 2 | 3 | 4; label: string } {
  if (!v) return { level: 0, label: '' };
  const level = PASSWORD_RULES.filter(r => r.test(v)).length as 0 | 1 | 2 | 3 | 4;
  // Only the full set is actually accepted by the server, so nothing below 4
  // may read as "good enough".
  const labels = ['Too weak', 'Too weak', 'Weak', 'Almost there', 'Strong'];
  return { level, label: labels[level] };
}

/**
 * Short enough to fit a single-line TextInput — the full policy goes on the
 * helper line below the field (PASSWORD_POLICY_HINT), not in the placeholder.
 */
export const PASSWORD_PLACEHOLDER = 'Create a password';

/** Full policy, shown under the field before the user starts typing. */
export const PASSWORD_POLICY_HINT = 'Must include: 8+ characters, uppercase, number, symbol';
