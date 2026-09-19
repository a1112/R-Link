/**
 * 自定义 React Hooks
 */

import React, { useEffect } from "react";

// ============================================
// Supabase Hooks
// ============================================

export {
  useAuth,
  useRequireAuth,
  useSupabaseQuery,
  useSupabaseMutation,
  useSupabaseSubscription,
  useSupabaseRecord,
  useSupabaseUpload,
  useSupabasePublicUrl,
  type UseAuthReturn,
} from "./useSupabase";

// ============================================
// 通用 Hooks
// ============================================

/**
 * 浏览器后退导航 Hook
 * 监听浏览器后退按钮，触发自定义回调
 *
 * @param onBack - 后退时的回调函数
 * @param enable - 是否启用监听，默认为 true
 */
export const useBackNavigation = (onBack: () => void, enable: boolean = true) => {
  useEffect(() => {
    if (!enable) return;

    const handlePopState = (e: PopStateEvent) => {
      e.preventDefault();
      window.history.pushState(null, "", window.location.href);
      onBack();
    };

    window.history.pushState(null, "", window.location.href);
    window.addEventListener('popstate', handlePopState);

    const handleMouseUp = (e: MouseEvent) => {
      if (e.button === 3) {
        e.preventDefault();
      }
    };
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [enable, onBack]);
};

/**
 * 主题 Hook
 * 管理应用主题
 */
export const useTheme = (initialTheme: 'zinc' | 'light' = 'zinc') => {
  const [theme, setTheme] = React.useState(initialTheme);

  React.useEffect(() => {
    // 从 localStorage 读取保存的主题
    const saved = localStorage.getItem('theme') as 'zinc' | 'light' | null;
    if (saved) {
      setTheme(saved);
    }
  }, []);

  const changeTheme = (newTheme: 'zinc' | 'light') => {
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  return { theme, setTheme: changeTheme };
};

/**
 * 键盘快捷键 Hook
 *
 * @param key - 要监听的按键
 * @param callback - 触发时的回调函数
 * @param enable - 是否启用监听，默认为 true
 */
export const useKeyboard = (
  key: string,
  callback: () => void,
  enable: boolean = true
) => {
  useEffect(() => {
    if (!enable) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === key) {
        e.preventDefault();
        callback();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [key, callback, enable]);
};

/**
 * 防抖 Hook
 *
 * @param value - 要防抖的值
 * @param delay - 延迟时间（毫秒）
 */
export const useDebounce = <T>(value: T, delay: number = 300): T => {
  const [debouncedValue, setDebouncedValue] = React.useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

/**
 * 本地存储 Hook
 *
 * @param key - 存储键名
 * @param initialValue - 初始值
 */
export const useLocalStorage = <T>(key: string, initialValue: T): [T, (value: T) => void] => {
  const [storedValue, setStoredValue] = React.useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(error);
      return initialValue;
    }
  });

  const setValue = (value: T) => {
    try {
      setStoredValue(value);
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error(error);
    }
  };

  return [storedValue, setValue];
};
