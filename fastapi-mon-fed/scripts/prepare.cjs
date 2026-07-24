/**
 * CI / Vercel 上跳过 husky（无 .git 或无权写 hooks），仍执行 max setup。
 * 本地开发则两者都跑。
 */
const { execSync } = require('node:child_process');

const skipHusky =
  process.env.CI === '1' ||
  process.env.CI === 'true' ||
  !!process.env.VERCEL ||
  process.env.HUSKY === '0';

if (!skipHusky) {
  execSync('npx husky', { stdio: 'inherit' });
}

execSync('npx max setup', { stdio: 'inherit' });
