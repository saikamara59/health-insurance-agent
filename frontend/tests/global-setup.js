import { spawnSync } from 'node:child_process'

const COMPOSE_FILES = ['-f', '../docker-compose.yml', '-f', '../docker-compose.test.yml']
const COMPOSE_ENV = {
  ...process.env,
  ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || 'test-key-not-used',
  JWT_SECRET: process.env.JWT_SECRET || 'test-secret',
}

function dumpLogs() {
  spawnSync('docker', ['compose', ...COMPOSE_FILES, 'logs', 'backend', 'seed'], {
    stdio: 'inherit',
    env: COMPOSE_ENV,
  })
}

export default async function globalSetup() {
  console.log('🐳 Starting docker-compose test stack (core services)...')

  // Step 1: Bring up the long-running services and wait for them to be healthy.
  // We exclude the seed service here because it's a one-shot job that exits 0,
  // and --wait treats any exited container as a failure (Docker Compose v5).
  const upResult = spawnSync(
    'docker',
    [
      'compose', ...COMPOSE_FILES,
      'up', '-d', '--build', '--wait',
      'backend', 'frontend', 'redis',
    ],
    { stdio: 'inherit', env: COMPOSE_ENV }
  )
  if (upResult.status !== 0) {
    console.error('❌ docker compose up failed; dumping logs:')
    dumpLogs()
    throw new Error(`docker compose up failed with exit code ${upResult.status}`)
  }

  // Step 2: Run the seed (schema reset) as a one-shot and wait for it to finish.
  console.log('🌱 Running schema seed...')
  const seedResult = spawnSync(
    'docker',
    [
      'compose', ...COMPOSE_FILES,
      'run', '--rm', 'seed',
    ],
    { stdio: 'inherit', env: COMPOSE_ENV }
  )
  if (seedResult.status !== 0) {
    console.error('❌ seed failed; dumping logs:')
    dumpLogs()
    throw new Error(`seed failed with exit code ${seedResult.status}`)
  }

  console.log('✅ Stack up and seeded')
}
