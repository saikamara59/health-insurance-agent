import { spawnSync } from 'node:child_process'

export default async function globalSetup() {
  console.log('🐳 Starting docker-compose test stack...')
  const result = spawnSync(
    'docker',
    [
      'compose',
      '-f', '../docker-compose.yml',
      '-f', '../docker-compose.test.yml',
      'up', '-d', '--wait',
    ],
    {
      stdio: 'inherit',
      env: {
        ...process.env,
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || 'test-key-not-used',
        JWT_SECRET: process.env.JWT_SECRET || 'test-secret',
      },
    }
  )
  if (result.status !== 0) {
    console.error('❌ docker compose up failed; dumping logs:')
    spawnSync(
      'docker',
      ['compose', '-f', '../docker-compose.yml', '-f', '../docker-compose.test.yml', 'logs', 'backend', 'seed'],
      { stdio: 'inherit' }
    )
    throw new Error(`docker compose up failed with exit code ${result.status}`)
  }
  console.log('✅ Stack up and seeded')
}
