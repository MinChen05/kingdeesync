import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getConfig } from '../api/config';
import { getForms } from '../api/forms';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [config, setConfig] = useState(null);
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [initError, setInitError] = useState(null);

  const refreshConfig = useCallback(async () => {
    try {
      const res = await getConfig();
      setConfig(res.data);
    } catch (err) {
      console.error('Refresh config failed:', err);
    }
  }, []);

  const refreshForms = useCallback(async () => {
    try {
      const res = await getForms();
      setForms(res.data);
    } catch (err) {
      console.error('Refresh forms failed:', err);
    }
  }, []);

  useEffect(() => {
    Promise.allSettled([getConfig(), getForms()])
      .then(([cfgResult, formsResult]) => {
        const errors = [];

        if (cfgResult.status === 'fulfilled') {
          setConfig(cfgResult.value.data);
        } else {
          errors.push(`加载配置失败: ${cfgResult.reason.message ?? '未知错误'}`);
        }

        if (formsResult.status === 'fulfilled') {
          setForms(formsResult.value.data);
        } else {
          errors.push(`加载表单列表失败: ${formsResult.reason.message ?? '未知错误'}`);
        }

        if (errors.length > 0) {
          setInitError(errors.join('；'));
        }
      })
      .catch(err => {
        setInitError(`初始化异常: ${err.message ?? '未知错误'}`);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppContext.Provider value={{ config, forms, loading, initError, refreshConfig, refreshForms }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
