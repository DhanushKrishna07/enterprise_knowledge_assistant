/** Simple UUID v4 without external dependency. */
export function v4(): string {
  return crypto.randomUUID();
}
