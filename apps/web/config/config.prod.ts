import { join } from 'node:path';
import { defineConfig } from '@umijs/max';
import defaultSettings, { themeConfig } from './defaultSettings';
import routes from './routes';

const PUBLIC_PATH = '/';

const commitHash = process.env.COMMIT_HASH || '';

export default defineConfig({
  hash: true,
  publicPath: PUBLIC_PATH,
  routes,
  ignoreMomentLocale: true,
  fastRefresh: false,
  esbuildMinifyIIFE: true,
  title: '金蝶数据同步',
  layout: {
    locale: false,
    ...defaultSettings,
  },
  locale: {
    default: 'zh-CN',
    antd: false,
    baseNavigator: false,
  },
  antd: {
    appConfig: {},
    configProvider: {
      variant: 'filled',
      theme: themeConfig,
    },
  },
  headScripts: [{ src: join(PUBLIC_PATH, 'scripts/loading.js'), async: true }],
  plugins: [],
  exportStatic: {},
  define: {
    'process.env.CI': process.env.CI,
    'process.env.COMMIT_HASH': commitHash,
    __APP_VERSION__: require('./../package.json').version,
  },
}) as ReturnType<typeof defineConfig>;
