/**
 * 统一的状态管理
 * 使用Context + useReducer管理全局状态
 */

import React, { createContext, useContext, useReducer, type ReactNode } from 'react';

// ==================== 类型定义 ====================

export interface AppState {
  user: {
    id: string | null;
    name: string | null;
    email: string | null;
    token: string | null;
  };
  config: {
    api: any;
    system: any;
  };
  ui: {
    sidebarCollapsed: boolean;
    theme: 'light' | 'dark';
    language: string;
  };
  cache: {
    datasets: any[];
    tasks: any[];
    reports: any[];
    assistants: any[];
    metrics: any[];
    lastUpdated: Record<string, number>;
  };
}

type AppAction =
  | { type: 'SET_USER'; payload: Partial<AppState['user']> }
  | { type: 'SET_CONFIG'; payload: Partial<AppState['config']> }
  | { type: 'UPDATE_UI'; payload: Partial<AppState['ui']> }
  | { type: 'UPDATE_CACHE'; payload: { key: keyof AppState['cache']; data: any[] } }
  | { type: 'INVALIDATE_CACHE'; payload: keyof AppState['cache'] | 'all' }
  | { type: 'RESET_STATE' };

// ==================== 初始状态 ====================

const initialState: AppState = {
  user: {
    id: localStorage.getItem('user_id'),
    name: localStorage.getItem('user_name'),
    email: localStorage.getItem('user_email'),
    token: localStorage.getItem('auth_token'),
  },
  config: {
    api: {},
    system: {},
  },
  ui: {
    sidebarCollapsed: false,
    theme: 'light',
    language: 'zh-CN',
  },
  cache: {
    datasets: [],
    tasks: [],
    reports: [],
    assistants: [],
    metrics: [],
    lastUpdated: {},
  },
};

// ==================== Reducer ====================

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_USER':
      const userPayload = action.payload;
      // 同步到localStorage
      if (userPayload.id !== undefined) {
        localStorage.setItem('user_id', userPayload.id || '');
      }
      if (userPayload.token !== undefined) {
        localStorage.setItem('auth_token', userPayload.token || '');
      }
      if (userPayload.name !== undefined) {
        localStorage.setItem('user_name', userPayload.name || '');
      }
      if (userPayload.email !== undefined) {
        localStorage.setItem('user_email', userPayload.email || '');
      }

      return {
        ...state,
        user: {
          ...state.user,
          ...userPayload,
        },
      };

    case 'SET_CONFIG':
      return {
        ...state,
        config: {
          ...state.config,
          ...action.payload,
        },
      };

    case 'UPDATE_UI':
      return {
        ...state,
        ui: {
          ...state.ui,
          ...action.payload,
        },
      };

    case 'UPDATE_CACHE':
      return {
        ...state,
        cache: {
          ...state.cache,
          [action.payload.key]: action.payload.data,
          lastUpdated: {
            ...state.cache.lastUpdated,
            [action.payload.key]: Date.now(),
          },
        },
      };

    case 'INVALIDATE_CACHE':
      if (action.payload === 'all') {
        return {
          ...state,
          cache: {
            ...initialState.cache,
          },
        };
      }
      return {
        ...state,
        cache: {
          ...state.cache,
          [action.payload]: [],
          lastUpdated: {
            ...state.cache.lastUpdated,
            [action.payload]: 0,
          },
        },
      };

    case 'RESET_STATE':
      // 清除localStorage
      localStorage.removeItem('user_id');
      localStorage.removeItem('user_name');
      localStorage.removeItem('user_email');
      localStorage.removeItem('auth_token');
      return initialState;

    default:
      return state;
  }
}

// ==================== Context ====================

const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

// ==================== Provider ====================

interface AppProviderProps {
  children: ReactNode;
}

export function AppProvider({ children }: AppProviderProps) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

// ==================== Hook ====================

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
}

// ==================== 便捷Hook ====================

export function useUser() {
  const { state, dispatch } = useAppContext();
  const setUser = (payload: Partial<AppState['user']>) => {
    dispatch({ type: 'SET_USER', payload });
  };
  return { user: state.user, setUser };
}

export function useConfig() {
  const { state, dispatch } = useAppContext();
  const setConfig = (payload: Partial<AppState['config']>) => {
    dispatch({ type: 'SET_CONFIG', payload });
  };
  return { config: state.config, setConfig };
}

export function useUI() {
  const { state, dispatch } = useAppContext();
  const updateUI = (payload: Partial<AppState['ui']>) => {
    dispatch({ type: 'UPDATE_UI', payload });
  };
  return { ui: state.ui, updateUI };
}

export function useCache() {
  const { state, dispatch } = useAppContext();

  const updateCache = <T,>(key: keyof AppState['cache'], data: T[]) => {
    dispatch({ type: 'UPDATE_CACHE', payload: { key, data } });
  };

  const invalidateCache = (key: keyof AppState['cache'] | 'all' = 'all') => {
    dispatch({ type: 'INVALIDATE_CACHE', payload: key });
  };

  const isCacheValid = (key: keyof AppState['cache'], ttl: number = 5 * 60 * 1000) => {
    const lastUpdated = state.cache.lastUpdated[key] || 0;
    return Date.now() - lastUpdated < ttl;
  };

  return {
    cache: state.cache,
    updateCache,
    invalidateCache,
    isCacheValid,
  };
}

// ==================== 缓存策略Hook ====================

export function useCachedData<T>(
  key: keyof AppState['cache'],
  fetcher: () => Promise<T[]>,
  ttl: number = 5 * 60 * 1000 // 默认5分钟
) {
  const { cache, updateCache, isCacheValid } = useCache();

  const data = cache[key] as T[] | undefined;
  const isValid = data && isCacheValid(key, ttl);
  const loading = !isValid;

  const refetch = async () => {
    try {
      const result = await fetcher();
      updateCache(key, result);
      return result;
    } catch (error) {
      console.error(`Failed to fetch ${key}:`, error);
      throw error;
    }
  };

  // 如果缓存无效，触发数据获取
  React.useEffect(() => {
    if (!isValid) {
      refetch();
    }
  }, [key, isValid]);

  return {
    data: data || [],
    loading,
    refetch,
    isValid,
  };
}

// ==================== 全局状态初始化 ====================

export function initializeApp() {
  // 从localStorage恢复状态
  const savedUser = {
    id: localStorage.getItem('user_id'),
    name: localStorage.getItem('user_name'),
    email: localStorage.getItem('user_email'),
    token: localStorage.getItem('auth_token'),
  };

  return {
    user: savedUser,
  };
}