import client from './client';

export function getDiagnostics() {
  return client.get('/diagnostics').then(r => r.data);
}

export function testConnections() {
  return client.post('/diagnostics/test-connections').then(r => r.data);
}
