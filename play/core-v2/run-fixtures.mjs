#!/usr/bin/env node
// node play/core-v2/run-fixtures.mjs
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runF01, runF02, runF03, runF04a, runF04b, runF05, runF06, runF07, allPassed } from './fixtures.js';

const here = dirname(fileURLToPath(import.meta.url));

function displayStatus(r) {
  if (r.status === 'valid') return 'valid';
  const code = r.diagnostics[0]?.code;
  return code ? `${r.status}:${code}` : r.status;
}

function row(id, result) {
  const r = result.report;
  const failed = result.checks.filter((c) => !c.ok);
  const pass = failed.length === 0 ? 'PASS' : 'FAIL';
  const seam = r.seam?.overlapMm != null ? r.seam.overlapMm.toFixed(2) : '-';
  const cov = r.sheet.coveredLengthMm.toFixed(2);
  const ph = r.sheet.phantomLengthMm.toFixed(3);
  const u = `${r.sheet.uMinMm.toFixed(1)}–${r.sheet.uMaxMm.toFixed(1)}`;
  const h = r.hashes.winding ? r.hashes.winding.slice(0, 10) : '-';
  const nDiag = r.diagnostics.length;
  const why = failed.map((c) => `${c.name}:${c.detail}`).join('; ');
  return { id, pass, shown: displayStatus(r), cov, ph, u, seam, h, nDiag, why, report: r, checks: result.checks };
}

const f01 = row('F01', runF01());
const f02 = row('F02', runF02());
const f03run = runF03();
const f03rows = f03run.series.map((s) => row(`F03-${s.uMm}`, {
  report: s.report,
  checks: f03run.checks.filter((c) => c.name.startsWith(`F03-${s.uMm}`) || c.name.startsWith('F03-cont')),
}));
const f03 = { ...row('F03', { report: f03run.series[2].report, checks: f03run.checks }), series: f03run.series };
const f04a = row('F04a', runF04a());
const f04b = row('F04b', runF04b());
const f05run = runF05();
const f05 = row('F05', f05run);
const f06run = runF06();
const f06 = row('F06', { report: f06run.report, checks: f06run.checks });
const f07run = runF07();
const f07 = row('F07', { report: f07run.report, checks: f07run.checks });
const f01b = row('F01-repeat', runF01());
const f02b = row('F02-repeat', runF02());
const f04a2 = row('F04a-repeat', runF04a());
const f04b2 = row('F04b-repeat', runF04b());

const all = [f01, f02, ...f03rows, f04a, f04b, f05, f06, f07, f01b, f02b, f04a2, f04b2];
const lines = [
  'id            gate  status                           covered  phantom  uMm          seamMm  hash       diag',
  ...all.map((x) =>
    `${x.id.padEnd(14)}${x.pass.padEnd(6)}${x.shown.padEnd(32)}${x.cov.padEnd(9)}${x.ph.padEnd(9)}${x.u.padEnd(13)}${String(x.seam).padEnd(8)}${x.h.padEnd(11)}${x.nDiag}${x.why ? '  ' + x.why : ''}`,
  ),
];
console.log(lines.join('\n'));

if (f01.report.hashes.winding !== f01b.report.hashes.winding) {
  console.error('F06: F01 winding hash mismatch across reruns');
}
if (f02.report.hashes.winding !== f02b.report.hashes.winding) {
  console.error('F06: F02 winding hash mismatch across reruns');
}
if (f04a.report.diagnostics[0]?.code !== f04a2.report.diagnostics[0]?.code) {
  console.error('F06: F04a diagnostic mismatch');
}
if (f04b.report.diagnostics[0]?.code !== f04b2.report.diagnostics[0]?.code) {
  console.error('F06: F04b diagnostic mismatch');
}

const outDir = join(here, 'reports');
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'F01.json'), JSON.stringify(f01.report, null, 2));
writeFileSync(join(outDir, 'F02.json'), JSON.stringify(f02.report, null, 2));
writeFileSync(join(outDir, 'F03.json'), JSON.stringify(f03run.series.map((s) => ({
  uMm: s.uMm,
  status: s.report.status,
  diagnostics: s.report.diagnostics,
  placementWindowMm: s.report.placementWindowMm,
  visiblePatches: s.report.visiblePatches,
  hashes: s.report.hashes,
})), null, 2));
writeFileSync(join(outDir, 'F04a.json'), JSON.stringify(f04a.report, null, 2));
writeFileSync(join(outDir, 'F04b.json'), JSON.stringify(f04b.report, null, 2));
writeFileSync(join(outDir, 'F05.json'), JSON.stringify({
  abc: { status: f05run.abc.report.status, hashes: f05run.abc.report.hashes, visiblePatches: f05run.abc.report.visiblePatches },
  cab: { status: f05run.cab.report.status, hashes: f05run.cab.report.hashes, visiblePatches: f05run.cab.report.visiblePatches },
}, null, 2));
writeFileSync(join(outDir, 'F07.json'), JSON.stringify({
  steps: f07run.steps.map((s) => ({
    uMm: s.uMm,
    status: s.a.report.status,
    visiblePatches: s.a.report.visiblePatches,
  })),
  overlap: { status: f07run.overlap.report.status, diagnostics: f07run.overlap.report.diagnostics },
}, null, 2));

const failed = [f01, f02, f03, f04a, f04b, f05, f06, f07].some((x) => x.pass !== 'PASS')
  || !allPassed(f03run.checks)
  || !allPassed(f05run.checks)
  || !allPassed(f06run.checks)
  || !allPassed(f07run.checks)
  || f01.report.hashes.winding !== f01b.report.hashes.winding
  || f02.report.hashes.winding !== f02b.report.hashes.winding
  || f04a.report.diagnostics[0]?.code !== f04a2.report.diagnostics[0]?.code
  || f04b.report.diagnostics[0]?.code !== f04b2.report.diagnostics[0]?.code;
process.exit(failed ? 1 : 0);
