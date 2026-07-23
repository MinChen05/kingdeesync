import client from './client';

export function startSync(forms, syncType) {
  return client.post('/sync/start', { forms, sync_type: syncType }).then(r => r.data);
}

export function getSyncStatus(runId) {
  const params = runId ? { run_id: runId } : {};
  return client.get('/sync/status', { params }).then(r => r.data);
}

export function stopSync(runId) {
  const params = runId ? { run_id: runId } : {};
  return client.post('/sync/stop', null, { params }).then(r => r.data);
}
