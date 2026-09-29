import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import 'antd/dist/reset.css';
import './styles.css';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#2563eb',
          colorInfo: '#38bdf8',
          colorSuccess: '#14b8a6',
          colorWarning: '#f59e0b',
          colorText: '#10233f',
          colorTextSecondary: '#60748f',
          colorBgLayout: '#eef7ff',
          colorBorder: '#c9dcff',
          borderRadius: 12,
          fontFamily:
            '"Inter", "SF Pro Display", "PingFang SC", "Microsoft YaHei", Arial, sans-serif'
        },
        components: {
          Card: {
            borderRadiusLG: 14,
            paddingLG: 24
          },
          Button: {
            borderRadius: 10
          },
          Input: {
            borderRadius: 14,
            activeBorderColor: '#38bdf8',
            hoverBorderColor: '#60a5fa'
          },
          Menu: {
            itemBorderRadius: 999,
            horizontalItemSelectedColor: '#0f4bd8'
          }
        }
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
