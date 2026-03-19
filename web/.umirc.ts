import path from 'path';
import TerserPlugin from 'terser-webpack-plugin';
import { defineConfig } from 'umi';
import { appName } from './src/conf.json';
import routes from './src/routes';
const ESLintPlugin = require('eslint-webpack-plugin');

export default defineConfig({
  title: appName,
  outputPath: 'dist',
  alias: { '@parent': path.resolve(__dirname, '../') },
  npmClient: 'npm',
  base: '/',
  routes,
  publicPath: '/',
  esbuildMinifyIIFE: true,
  icons: {},
  hash: true,
  favicons: ['/logo.svg'],
  headScripts: [{ src: '/iconfont.js', defer: true }],
  clickToComponent: {},
  history: {
    type: 'browser',
  },
  plugins: [
    '@react-dev-inspector/umi4-plugin',
    '@umijs/plugins/dist/tailwindcss',
  ],
  jsMinifier: 'none', // Fixed the issue that the page displayed an error after packaging lexical with terser
  lessLoader: {
    modifyVars: {
      hack: `true; @import "~@/less/index.less";`,
    },
  },
  devtool: 'source-map',
  copy: [
    { from: 'src/conf.json', to: 'dist/conf.json' },
    { from: 'node_modules/monaco-editor/min/vs/', to: 'dist/vs/' },
  ],
  proxy: {
    // KnowFlow API - 企业功能 API，路由到 KnowFlow 后端
    '/api/knowflow/v1': {
      target: 'http://127.0.0.1:5000',
      changeOrigin: true,
      pathRewrite: {
        '^/api/knowflow/v1': '/api/v1', // 重写路径匹配 nginx 配置
      },
    },
    // RAGFlow SDK API - 对外提供的 SDK API，路由到 RAGFlow
    '/api/v1': {
      target: 'http://127.0.0.1:9380',
      changeOrigin: true,
    },
    '/v1': {
      target: 'http://127.0.0.1:9380',
      changeOrigin: true,
    },
    '/minio': {
      target: 'http://127.0.0.1:9000',
      changeOrigin: true,
      pathRewrite: {
        '^/minio': '', // 去掉 /minio 前缀
      },
    },
  },

  chainWebpack(memo, args) {
    memo.module.rule('markdown').test(/\.md$/).type('asset/source');

    memo.optimization.minimizer('terser').use(TerserPlugin); // Fixed the issue that the page displayed an error after packaging lexical with terser

    // memo.plugin('eslint').use(ESLintPlugin, [
    //   {
    //     extensions: ['js', 'ts', 'tsx'],
    //     failOnError: true,
    //     exclude: ['**/node_modules/**', '**/mfsu**', '**/mfsu-virtual-entry**'],
    //     files: ['src/**/*.{js,ts,tsx}'],
    //   },
    // ]);

    return memo;
  },
  tailwindcss: {},
});
