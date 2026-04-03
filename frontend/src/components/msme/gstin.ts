const GSTIN_PATTERN = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

export function normalizeGstin(value: string): string {
  return (value || '').trim().toUpperCase();
}

export function isValidGstin(value: string): boolean {
  return GSTIN_PATTERN.test(normalizeGstin(value));
}

export function gstinValidationMessage(value: string): string | null {
  const normalized = normalizeGstin(value);
  if (!normalized) return 'Enter a GSTIN to run scoring.';
  if (!isValidGstin(normalized)) {
    return 'Invalid GSTIN format. Use 15 characters: state code + PAN + entity code + Z + checksum.';
  }
  return null;
}
