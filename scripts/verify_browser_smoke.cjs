/* Opt-in real UI check. No API interception or credential output.
 * --generate-new additionally consumes real model calls.
 * A running frontend/backend and a disposable account with a saved 内容运营
 * roadmap (first task checked, second unchecked) are required. See demo docs.
 */
const { chromium } = require('../frontend/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const args = process.argv.slice(2);
function option(name, fallback) {
  const position = args.indexOf(name);
  return position < 0 ? fallback : args[position + 1];
}
const root = path.resolve(__dirname, '..');
const base = new URL(option('--base-url', 'http://localhost:5173'));
assert(['localhost', '127.0.0.1', '[::1]'].includes(base.hostname) &&
  !base.username && !base.password && !base.search && !base.hash && base.pathname === '/',
  'Only a local origin is accepted');
const credentialsFile = path.resolve(root, option('--credentials-file', 'tmp/browser-account.json'));
const outputDir = path.resolve(root, option('--output-dir', 'tmp/browser-smoke'));
for (const target of [credentialsFile, outputDir]) {
  assert(!path.relative(root, target).startsWith('..') && !path.isAbsolute(path.relative(root, target)),
    'Files must remain within this repository');
}

(async () => {
  const credentials = JSON.parse(await fs.readFile(credentialsFile, 'utf8'));
  assert(typeof credentials.username === 'string' && credentials.username.startsWith('pilot_live_') &&
    typeof credentials.password === 'string' && Number.isSafeInteger(credentials.roadmap_id),
    'Use a disposable verifier account with a saved roadmap');
  await fs.mkdir(outputDir, { recursive: true });
  const result = { started_at: new Date().toISOString(), status: 'running',
    frontend_origin: base.origin, mode: 'real API, saved synthetic roadmap; no intercepted requests',
    checks: [], page_errors: [], screenshots: [] };
  let browser;
  const check = (name, evidence) => result.checks.push({ name, status: 'passed', evidence });
  try {
    browser = await chromium.launch({ headless: true, channel: option('--channel', undefined) });
    result.browser_version = browser.version();
    const context = await browser.newContext({ viewport: { width: 1365, height: 1000 }, acceptDownloads: true });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', error => result.page_errors.push(error.message));
    await page.goto(new URL('/login', base).href);
    await page.getByPlaceholder('username', { exact: true }).fill(credentials.username);
    await page.getByPlaceholder('password', { exact: true }).fill(credentials.password);
    await page.getByRole('button', { name: /进入职业成长中心/ }).click();
    await page.waitForURL('**/dashboard');
    await page.locator('canvas').first().waitFor({ state: 'visible' });
    check('login_and_dashboard_chart_render', { route: '/dashboard', canvases: await page.locator('canvas').count() });
    await page.goto(new URL('/recommendations', base).href);
    await page.getByRole('heading', { name: '内容运营', exact: true }).waitFor();
    // Inspect visible role headings: exact class names may differ between layouts.
    const roles = await page.locator('h3').allTextContents();
    assert(roles.includes('内容运营') && roles.includes('市场助理') && roles.includes('新媒体运营'));
    assert(!roles.includes('招聘助理'));
    check('recommendations_stay_in_marketing_domain', roles);
    await page.getByText('查看工作任务、依据与适用范围', { exact: true }).first().click();
    await page.getByRole('link', { name: /教育部2025/ }).first().waitFor();
    await page.getByRole('link', { name: /教育部2025/ }).first().scrollIntoViewIfNeeded();
    check('source_links_and_version_visible', { version: 'manual-pilot-2026-10-12-v2',
      sourceLinks: await page.getByRole('link', { name: /教育部2025/ }).count() });
    assert((await page.locator('body').innerText()).includes('manual-pilot-2026-10-12-v2'));
    await page.screenshot({ path: path.join(outputDir, 'recommendations.png'), fullPage: true, animations: 'disabled' });
    result.screenshots.push('recommendations.png');
    const roadmapUrl = new URL(`/roadmap?role=${encodeURIComponent('内容运营')}&history_id=${credentials.roadmap_id}`, base).href;
    await page.goto(roadmapUrl);
    const boxes = page.getByRole('checkbox');
    await boxes.nth(1).waitFor();
    assert.equal(await boxes.count(), 2);
    assert(await boxes.nth(0).isChecked());
    assert(!(await boxes.nth(1).isChecked()));
    check('actual_saved_tasks_restore', { roadmap_id: credentials.roadmap_id, taskCount: 2 });
    const saveProgress = () => page.waitForResponse(response => response.request().method() === 'PUT' && response.url().includes('/progress'));
    let saved = saveProgress();
    await boxes.nth(1).check();
    assert.equal((await saved).status(), 200);
    await page.reload();
    await boxes.nth(1).waitFor();
    assert(await boxes.nth(1).isChecked());
    check('progress_check_survives_reload', true);
    saved = saveProgress();
    await boxes.nth(1).uncheck();
    assert.equal((await saved).status(), 200);
    await page.reload();
    await boxes.nth(1).waitFor();
    assert(!(await boxes.nth(1).isChecked()));
    check('progress_uncheck_survives_reload', true);
    const downloading = page.waitForEvent('download');
    await page.getByRole('button', { name: /保存本次规划结果/ }).click();
    const download = await downloading;
    await download.saveAs(path.join(outputDir, 'browser-export.md'));
    const exported = await fs.readFile(path.join(outputDir, 'browser-export.md'), 'utf8');
    assert(exported.includes('内容运营') && exported.includes('manual-pilot-2026-10-12-v2') && exported.includes('[x]') && exported.includes('[ ]'));
    check('native_browser_download_contains_current_progress_and_source', { bytes: Buffer.byteLength(exported), filename: download.suggestedFilename() });
    await page.screenshot({ path: path.join(outputDir, 'saved-roadmap.png'), fullPage: true, animations: 'disabled' });
    result.screenshots.push('saved-roadmap.png');
    if (args.includes('--generate-new')) {
      const generation = page.waitForResponse(response => response.request().method() === 'POST' &&
        response.url().includes('/api/agent/learning-path'), { timeout: 220000 });
      await page.getByRole('button', { name: /生成新的学习路径版本/ }).click();
      const response = await generation;
      assert.equal(response.status(), 200);
      const generated = await response.json();
      assert(generated.id !== credentials.roadmap_id && generated.target_role === '内容运营');
      assert.equal(generated.milestones.length, 1);
      assert.equal(generated.milestones[0].focus_targets.length, 2);
      result.generated_roadmap = generated;
      await page.getByText('本路径使用的标准依据', { exact: true }).waitFor();
      check('real_model_generation_through_ui_saves_new_version', { roadmap_id: generated.id,
        app_model_calls: generated.generation_attempts, source_version: generated.standard_source.version });
      await page.screenshot({ path: path.join(outputDir, 'generated-roadmap.png'), fullPage: true, animations: 'disabled' });
      result.screenshots.push('generated-roadmap.png');
    }
    assert.equal(result.page_errors.length, 0);
    check('no_javascript_page_errors_in_checked_routes', true);
    result.status = 'passed';
    await context.close();
  } catch (error) {
    result.status = 'failed';
    // Do not serialize errors containing submitted form values or credentials.
    result.error_type = error.name;
    console.error('Browser smoke failed:', error.name, String(error.message)
      .replaceAll(credentials.password, '[redacted]').replaceAll(credentials.username, '[synthetic account]').slice(0,2000));
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    result.finished_at = new Date().toISOString();
    await fs.writeFile(path.join(outputDir, 'browser-results.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(`Browser smoke ${result.status}; ${result.checks.length} completed checks`);
  }
})().catch(() => { console.error('Browser smoke setup failed'); process.exitCode = 1; });
