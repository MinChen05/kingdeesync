import client from './client';

export function getConfig() {
  return client.get('/config').then(r => r.data);
}

export function updateConfig(payload) {
  return client.put('/config', payload).then(r => r.data);
}
