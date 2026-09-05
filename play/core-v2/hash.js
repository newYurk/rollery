// Canonicalize + digest. Erratum 011.
// Domain: recipe / winding / section — never FixtureReport.

import { createHash } from 'node:crypto';

export function canonicalize(value) {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new Error('canonicalize: non-finite number');
    }
    return JSON.stringify(value);
  }
  if (typeof value === 'string' || typeof value === 'boolean') {
    return JSON.stringify(value);
  }
  if (value === null) return 'null';
  if (value === undefined) {
    throw new Error('canonicalize: undefined');
  }
  if (typeof DataView !== 'undefined' && value instanceof DataView) {
    throw new Error('canonicalize: DataView не поддерживается — сериализуйте поля явно');
  }
  if (Array.isArray(value) || ArrayBuffer.isView(value)) {
    const arr = Array.isArray(value) ? value : Array.from(value);
    return '[' + arr.map(canonicalize).join(',') + ']';
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return '{' + keys.map((k) => JSON.stringify(k) + ':' + canonicalize(value[k])).join(',') + '}';
  }
  throw new Error('canonicalize: unsupported type ' + typeof value);
}

export function digest(canonicalString) {
  return createHash('sha256').update(canonicalString, 'utf8').digest('hex');
}

export function hashValue(value) {
  return digest(canonicalize(value));
}
