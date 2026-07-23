import client from './client';

export function getHistory(params) {
  return client.get('/history', { params }).then(r => r.data);
}

export function getRunDetails(runId) {
  return client.get(`/history/runs/${runId}/details`).then(r => r.data);
}
