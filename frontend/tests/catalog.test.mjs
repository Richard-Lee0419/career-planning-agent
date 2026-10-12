import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const ts = require('typescript');

test('simultaneous recommendation requests stay separate by domain and deduplicate only within the same domain', async () => {
  const source = readFileSync(new URL('../src/api/recommendations.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const api = {};
  const requests = [];
  vm.runInNewContext(compiled, { exports: api, require: (path) => path === './client'
    ? { apiClient: { get: (_url, config) => new Promise((resolve) => requests.push({ domain: config.params.domain, resolve })) } }
    : { useAuthStore: { getState: () => ({ token: 'test-user' }) } } });
  const marketing = api.fetchRecommendations('marketing_content');
  const marketingAgain = api.fetchRecommendations('marketing_content');
  const hr = api.fetchRecommendations('human_resources');
  assert.deepEqual(requests.map((request) => request.domain), ['marketing_content', 'human_resources']);
  requests[0].resolve({ data: { data: [{ role_name: '内容运营' }] } });
  requests[1].resolve({ data: { data: [{ role_name: '招聘助理' }] } });
  assert.equal((await marketing).data[0].role_name, '内容运营');
  assert.equal((await marketingAgain).data[0].role_name, '内容运营');
  assert.equal((await hr).data[0].role_name, '招聘助理');
});
