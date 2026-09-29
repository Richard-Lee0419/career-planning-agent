import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const ts = require('typescript');

function loadTypeScript(relativePath, globals = {}) {
  const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX }
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    require: () => ({}),
    ...globals
  });
  return exports;
}

test('private draft keys require a valid user ID and never reuse the legacy key', () => {
  const removed = [];
  const storage = loadTypeScript('../src/utils/privateStorage.ts', {
    localStorage: { removeItem: (key) => removed.push(key) }
  });
  assert.equal(storage.getUserStorageKey('career-assessment-draft', 12), 'career-assessment-draft:user:12');
  assert.equal(storage.getUserStorageKey('career-assessment-draft', 13), 'career-assessment-draft:user:13');
  assert.equal(storage.getUserStorageKey('career-assessment-draft', null), null);
  storage.clearLegacyPrivateStorage();
  assert.deepEqual(removed, ['career-assessment-draft', 'career-roadmap-completed']);
});

test('untrusted graph HTML is escaped and a cyclic graph cannot recurse indefinitely', () => {
  const graph = loadTypeScript('../src/components/CareerTree.tsx');
  assert.equal(graph.escapeHtml('<img src=x onerror="1">'), '&lt;img src=x onerror=&quot;1&quot;&gt;');

  const level = (id, nextLevels) => ({
    id, level: '初级', title: '工程师', status: 'acquired', salaryRange: '10K',
    coreSkills: [{ name: 'React', isMastered: true }], nextLevels
  });
  const nodes = [level('a', ['b']), level('b', ['a'])];
  assert.equal(graph.isCareerGraphData({ levels: nodes }), true);
  assert.deepEqual(Array.from(graph.makeTree(nodes)), []);
  assert.equal(graph.isCareerGraphData({ levels: [{ ...nodes[0], nextLevels: 'b' }] }), false);
  assert.equal(graph.isCareerGraphData({ levels: Array.from({ length: 61 }, (_, i) => level(`${i}`, [])) }), false);
});
