#!/usr/bin/env node
// node play/core-v2/run-fixtures.mjs
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runF01, runF02, allPassed } from './fixtures.js';

const here = dirname(fileURLToPath(import.meta.url));

function row(id, result) {
  const r = result.report;
  const failed = result.checks.filter((c) => !c.ok);
  const status = r.status === 'valid' && failed.length === 0 ? 'PASS' : 'FAIL';
  const seam = r.seam ? r.seam.overlapMm.toFixed(2) : '-';
  const cov = r.sheet.coveredLengthMm.toFixed(2);
  const ph = r.sheet.phantomLengthMm.toFixed(3);
  const u = `${r.sheet.uMinMm.toFixed(1)}–${r.sheet.uMaxMm.toFixed(1)}`;
  const h = r.hashes.winding ? r.hashes.winding.slice(0, 10) : '-';
  const nDiag = r.diagnostics.length;
  const why = failed.map((c) => `${c.name}:${c.detail}`).join('; ');
  return { id, status, cov, ph, u, seam, h, nDiag, why, report: r, checks: result.checks };
}

const f01 = row('F01', runF01());
const f02 = row('F02', runF02());
const f01b = row('F01-repeat', runF01());
const f02b = row('F02-repeat', runF02());

const lines = [
  'id          status  covered  phantom  uMm          seamMm  hash       diag',
  ...[f01, f02, f01b, f02b].map((x) =>
    `${x.id.padEnd(12)}${x.status.padEnd(8)}${x.cov.padEnd(9)}${x.ph.padEnd(9)}${x.u.padEnd(13)}${String(x.seam).padEnd(8)}${x.h.padEnd(11)}${x.nDiag}${x.why ? '  ' + x.why : ''}`,
  ),
];
console.log(lines.join('\n'));

if (f01.report.hashes.winding !== f01b.report.hashes.winding) {
  console.error('F06: F01 winding hash mismatch across reruns');
}
if (f02.report.hashes.winding !== f02b.report.hashes.winding) {
  console.error('F06: F02 winding hash mismatch across reruns');
}

const outDir = join(here, 'reports');
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'F01.json'), JSON.stringify(f01.report, null, 2));
writeFileSync(join(outDir, 'F02.json'), JSON.stringify(f02.report, null, 2));

const failed = [f01, f02].some((x) => x.status !== 'PASS')
  || f01.report.hashes.winding !== f01b.report.hashes.winding
  || f02.report.hashes.winding !== f02b.report.hashes.winding;
process.exit(failed ? 1 : 0);
