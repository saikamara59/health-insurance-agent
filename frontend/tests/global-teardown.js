import { spawnSync } from 'node:child_process'

export default async function globalTeardown() {
  console.log('🐳 Tearing down docker-compose test stack...')
  spawnSync(
    'docker',
    [
      'compose',
      '-f', '../docker-compose.yml',
      '-f', '../docker-compose.test.yml',
      'down', '-v', '--remove-orphans',
    ],
    { stdio: 'inherit' }
  )
}
