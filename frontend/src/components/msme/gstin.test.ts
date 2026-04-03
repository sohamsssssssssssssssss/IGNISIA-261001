import { describe, expect, it } from 'vitest';

import { gstinValidationMessage, isValidGstin, normalizeGstin } from './gstin';

describe('gstin helpers', () => {
  it('normalizes lowercase input', () => {
    expect(normalizeGstin('29clean5678b1z2')).toBe('29CLEAN5678B1Z2');
  });

  it('accepts valid gstin values', () => {
    expect(isValidGstin('29CLEAN5678B1Z2')).toBe(true);
  });

  it('rejects malformed gstin values', () => {
    expect(gstinValidationMessage('123')).toMatch(/Invalid GSTIN format/i);
  });
});
