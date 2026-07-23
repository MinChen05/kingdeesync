import { useState, useEffect } from 'react';
import { getDiagnostics } from '../../api/diagnostics';

export default function StatusBadge() {
  const [status, setStatus] = useState('loading'); // loading | ok | degraded | error

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const res = await getDiagnostics();
        if (cancelled) return;

        const d = res.data || res;
        const apiOk = d.kingdee_api?.connected ?? d.kingdee_api?.status === 'ok';
        const dbOk = d.database?.connected ?? d.database?.status === 'ok';

        if (apiOk && dbOk) {
          setStatus('ok');
        } else if (apiOk || dbOk) {
          setStatus('degraded');
        } else {
          setStatus('error');
        }
      } catch {
        if (!cancelled) setStatus('error');
      }
    };

    check();
    const interval = setInterval(check, 30000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const variants = {
    loading: { bg: 'bg-white/10', text: 'text-paper/60', label: '检测中' },
    ok: { bg: 'bg-success/20', text: 'text-success', label: '就绪' },
    degraded: { bg: 'bg-warning/20', text: 'text-warning', label: '部分异常' },
    error: { bg: 'bg-critical/20', text: 'text-critical', label: '异常' },
  };

  const v = variants[status] || variants.loading;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${v.bg} ${v.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${status === 'ok' ? 'bg-success animate-pulse' : status === 'error' ? 'bg-critical' : 'bg-current'}`} />
      {v.label}
    </span>
  );
}
