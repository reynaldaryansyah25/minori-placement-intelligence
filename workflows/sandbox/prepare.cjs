// Credentials are created only on the private server, imported encrypted, then removed from tmpfs.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const home = '/home/node/.n8n';
fs.mkdirSync(home, { recursive: true, mode: 0o700 });
const marker = path.join(home, '.minori-n8n-sandbox');
if (!fs.existsSync(marker) && fs.existsSync(path.join(home, 'database.sqlite'))) {
  throw new Error('Refusing an unverified n8n volume');
}
fs.writeFileSync(marker, 'Isolated MINORI sandbox only\n', { mode: 0o600 });
if (!process.env.SANDBOX_WORKER_TOKEN || !process.env.N8N_ENCRYPTION_KEY) {
  throw new Error('Sandbox credentials must be configured on the server');
}
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'minori-n8n-'));
const file = path.join(temporary, 'credentials.json');
fs.writeFileSync(file, JSON.stringify([
  { id: 'MinoriSandboxApi', name: 'MINORI Sandbox HTTP', type: 'httpHeaderAuth',
    data: { name: 'Authorization', value: 'Bearer ' + process.env.SANDBOX_WORKER_TOKEN } },
  { id: 'MinoriSandboxSmtp', name: 'MINORI Sandbox Mailpit', type: 'smtp',
    data: { host: 'mailpit-sandbox', port: 1025, secure: false, disableStartTls: true,
      user: '', password: '' } },
]), { mode: 0o600 });
function run(args) {
  const result = spawnSync('n8n', args, { stdio: 'pipe', timeout: 120000 });
  if (result.status !== 0) throw new Error('Private n8n bootstrap failed at ' + args[0]);
}
try {
  run(['import:credentials', '--input=' + file]);
  run(['import:workflow', '--input=/opt/minori/reminders.json']);
  if (process.env.SANDBOX_N8N_POLL_ENABLED !== 'false') {
    run(['publish:workflow', '--id=MinoriSandboxReminders']);
  }
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
