import client from './client';

export function getTodayStats() {
  return client.get('/dashboard/today').then(r => r.data);
}

export function getTrend7d() {
  return client.get('/dashboard/trend/7d').then(r => r.data);
}

export function getTopForms7d(limit) {
  return client.get('/dashboard/top-forms/7d', { params: { limit } }).then(r => r.data);
}
