import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/globals.css';
import { initializeDesktopBackend } from './api/config';

initializeDesktopBackend().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}).catch((error) => {
  document.getElementById('root')!.textContent = `后台连接失败：${String(error)}`;
});
