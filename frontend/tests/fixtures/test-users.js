export function workerBroker(workerIndex) {
  const id = `e2e-worker-${workerIndex}`
  return {
    workerId: id,
    email: `${id}@healthflow.test`,
    password: 'TestWorker123!',
  }
}
