import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const ToastContext = createContext(null);

// Debounce: coalesce rapid API errors into single toast
const DEBOUNCE_MS = 1500;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const debounceTimer = useRef(null);
  const pendingError = useRef(null);

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Listen for centralized API errors
  useEffect(() => {
    const handler = (event) => {
      const { message } = event.detail || {};
      if (!message) return;

      // If same error recently shown, skip
      if (pendingError.current === message) return;
      pendingError.current = message;

      // Debounce: if another error comes within 1.5s, show the latest one
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }

      debounceTimer.current = setTimeout(() => {
        addToast(message, 'error');
        pendingError.current = null;
        debounceTimer.current = null;
      }, DEBOUNCE_MS);
    };

    window.addEventListener('api-error', handler);
    return () => {
      window.removeEventListener('api-error', handler);
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [addToast]);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 space-y-2 z-50">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold shadow-lg cursor-pointer transition-all ${
              t.type === 'error' ? 'bg-critical text-white' :
              t.type === 'success' ? 'bg-success text-white' :
              'bg-ink-deep text-white'
            }`}
            onClick={() => removeToast(t.id)}
          >
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
