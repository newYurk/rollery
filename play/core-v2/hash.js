// Canonicalize + digest. Erratum 011.
// Domain: recipe / winding / section — never FixtureReport.

import { createHash } from 'node:crypto';
import { canonicalize } from './canonical.js';

export { canonicalize } from './canonical.js';

export function digest(canonicalString) {
  return createHash('sha256').update(canonicalString, 'utf8').digest('hex');
}

export function hashValue(value) {
  return digest(canonicalize(value));
}
