import client from './client';

export function getForms() {
  return client.get('/forms').then(r => r.data);
}

export function updateForm(formName, payload) {
  return client.put(`/forms/${formName}`, payload).then(r => r.data);
}
