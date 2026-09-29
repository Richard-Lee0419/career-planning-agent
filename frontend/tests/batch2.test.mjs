import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = readFileSync(new URL('../src/utils/careerPlan.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const careerPlan = {};
vm.runInNewContext(compiled, { exports: careerPlan, require: () => ({}) });

test('recommendation cards use only server evidence scores and actual requirements', () => {
  const profile = { current_skills: ['React'], soft_skills: ['团队协作'], certificates: [],
    target_roles: ['前端工程师'], interests: ['设计'] };
  const match = { role_name: '前端开发工程师', score: 47, matched_skills: ['React'],
    missing_skills: ['TypeScript', 'Git'], matched_soft_skills: ['团队协作'], missing_soft_skills: [],
    target_preference: true, interest_relevant: false, evidence: '基于岗位标准' };
  const result = careerPlan.getCareerRecommendations(profile, [match]);
  assert.equal(result[0].match, 47);
  assert.deepEqual(Array.from(result[0].gaps), ['TypeScript', 'Git']);
  assert.equal(careerPlan.getCareerRecommendations(profile, [{ ...match, score: null }]).length, 0);
  assert.equal(careerPlan.getCareerRecommendations(profile, []).length, 0);
  assert.equal(careerPlan.roleNamesMatch('前端开发工程师', '前端工程师'), true);
});

test('assessment text keeps interests, soft skills and weekly learning time distinct', () => {
  const text = careerPlan.buildAssessmentProfileText({ interests: ['交互设计'], softSkills: ['团队协作'],
    skills: ['React'], weeklyTime: '每周 6-10 小时', targetRoles: ['前端工程师'] });
  assert.match(text, /兴趣方向：交互设计/);
  assert.match(text, /软素质：团队协作/);
  assert.match(text, /学习投入：每周 6-10 小时/);
});
