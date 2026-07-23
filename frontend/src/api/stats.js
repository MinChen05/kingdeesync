import client from './client';

export function getStatsSummary(fromDate, toDate) {
  const params = {};
  if (fromDate) params.from_date = fromDate;
  if (toDate) params.to_date = toDate;
  return client.get('/stats/summary', { params }).then(r => r.data);
}

export function getFormStats(fromDate, toDate, limit) {
  const params = { limit: limit || 20 };
  if (fromDate) params.from_date = fromDate;
  if (toDate) params.to_date = toDate;
  return client.get('/stats/forms', { params }).then(r => r.data);
}
