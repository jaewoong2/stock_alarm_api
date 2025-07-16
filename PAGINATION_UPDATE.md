# Pagination Migration Guide: Backend to Frontend with React Query

## Overview

This guide covers the migration from backend pagination to frontend pagination using React Query for better user experience and performance. The backend API endpoints have been updated to return all data without pagination, and pagination is now handled on the frontend using React Query's powerful data management capabilities.

## Changes Made

### Backend Changes

#### 1. Signal Router (`myapi/routers/signal_router.py`)
- **Removed**: `PaginatedSignalsResponse`, `PaginatedSignalJoinTickerResponse`, `PaginationRequest` imports
- **Updated**: `/get-signals` endpoint to return `List[SignalBaseResponse]` instead of `PaginatedSignalsResponse`
- **Updated**: `/date` endpoint to return `List[SignalJoinTickerResponse]` instead of `PaginatedSignalJoinTickerResponse`
- **Removed**: `page` and `page_size` parameters from `/date` endpoint

#### 2. Signal Schema (`myapi/domain/signal/signal_schema.py`)
- **Removed**: `PaginationRequest` class
- **Removed**: `PaginationResponse` class
- **Removed**: `PaginatedSignalsResponse` class
- **Removed**: `PaginatedSignalJoinTickerResponse` class
- **Updated**: `GetSignalRequest` to remove `pagination` field

#### 3. Signals Repository (`myapi/repositories/signals_repository.py`)
- **Updated**: `get_signals()` method to return all results with basic ordering
- **Updated**: `get_signals_with_ticker()` method to remove pagination parameters
- **Removed**: `get_signals_with_ticker_count()` method (no longer needed)

#### 4. DB Signal Service (`myapi/services/db_signal_service.py`)
- **Updated**: `get_all_signals()` to return `List[SignalBaseResponse]` 
- **Updated**: `get_signals_result()` to return `List[SignalJoinTickerResponse]`
- **Removed**: Pagination metadata generation logic

## Frontend Implementation with React Query

### 1. Installation

```bash
npm install @tanstack/react-query
# or
yarn add @tanstack/react-query
```

### 2. Setup Query Client

```jsx
// src/config/queryClient.js
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
    },
  },
});

// src/App.jsx
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './config/queryClient';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* Your app components */}
    </QueryClientProvider>
  );
}
```

### 3. API Service Functions

```jsx
// src/services/signalService.js
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

export const signalService = {
  // Get all signals
  getAllSignals: async (filters = {}) => {
    const response = await fetch(`${API_BASE_URL}/signals/get-signals`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify(filters),
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch signals');
    }
    
    return response.json();
  },

  // Get signals by date
  getSignalsByDate: async (date, symbols = '', strategyType = null) => {
    const params = new URLSearchParams({
      date,
      symbols,
      ...(strategyType && { strategy_type: strategyType }),
    });
    
    const response = await fetch(`${API_BASE_URL}/signals/date?${params}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch signals by date');
    }
    
    return response.json();
  },
};
```

### 4. Custom Hooks with React Query

```jsx
// src/hooks/useSignals.js
import { useQuery } from '@tanstack/react-query';
import { signalService } from '../services/signalService';

export const useSignals = (filters = {}) => {
  return useQuery({
    queryKey: ['signals', filters],
    queryFn: () => signalService.getAllSignals(filters),
    enabled: true,
  });
};

export const useSignalsByDate = (date, symbols = '', strategyType = null) => {
  return useQuery({
    queryKey: ['signals', 'by-date', date, symbols, strategyType],
    queryFn: () => signalService.getSignalsByDate(date, symbols, strategyType),
    enabled: !!date,
  });
};
```

### 5. Pagination Components

```jsx
// src/components/Pagination.jsx
import React from 'react';

const Pagination = ({ 
  currentPage, 
  totalItems, 
  itemsPerPage, 
  onPageChange 
}) => {
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  
  const getPaginationNumbers = () => {
    const delta = 2;
    const range = [];
    const rangeWithDots = [];
    
    for (let i = Math.max(2, currentPage - delta); 
         i <= Math.min(totalPages - 1, currentPage + delta); 
         i++) {
      range.push(i);
    }
    
    if (currentPage - delta > 2) {
      rangeWithDots.push(1, '...');
    } else {
      rangeWithDots.push(1);
    }
    
    rangeWithDots.push(...range);
    
    if (currentPage + delta < totalPages - 1) {
      rangeWithDots.push('...', totalPages);
    } else {
      if (totalPages > 1) {
        rangeWithDots.push(totalPages);
      }
    }
    
    return rangeWithDots;
  };

  if (totalPages <= 1) return null;

  return (
    <nav className="flex items-center justify-between border-t border-gray-200 px-4 py-3 sm:px-6">
      <div className="flex flex-1 justify-between sm:hidden">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Previous
        </button>
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Next
        </button>
      </div>
      <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-gray-700">
            Showing{' '}
            <span className="font-medium">
              {(currentPage - 1) * itemsPerPage + 1}
            </span>{' '}
            to{' '}
            <span className="font-medium">
              {Math.min(currentPage * itemsPerPage, totalItems)}
            </span>{' '}
            of{' '}
            <span className="font-medium">{totalItems}</span> results
          </p>
        </div>
        <div>
          <nav className="isolate inline-flex -space-x-px rounded-md shadow-sm">
            {getPaginationNumbers().map((number, index) => (
              <button
                key={index}
                onClick={() => typeof number === 'number' && onPageChange(number)}
                disabled={number === '...' || number === currentPage}
                className={`relative inline-flex items-center px-4 py-2 text-sm font-semibold ${
                  number === currentPage
                    ? 'z-10 bg-blue-600 text-white'
                    : number === '...'
                    ? 'text-gray-700'
                    : 'text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50'
                } ${index === 0 ? 'rounded-l-md' : ''} ${
                  index === getPaginationNumbers().length - 1 ? 'rounded-r-md' : ''
                }`}
              >
                {number}
              </button>
            ))}
          </nav>
        </div>
      </div>
    </nav>
  );
};

export default Pagination;
```

### 6. Signal List Component with Pagination

```jsx
// src/components/SignalList.jsx
import React, { useState, useMemo } from 'react';
import { useSignals } from '../hooks/useSignals';
import Pagination from './Pagination';
import LoadingSpinner from './LoadingSpinner';
import ErrorMessage from './ErrorMessage';

const SignalList = () => {
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(20);
  const [filters, setFilters] = useState({});

  const { data: signals = [], isLoading, error } = useSignals(filters);

  // Client-side pagination
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return signals.slice(startIndex, endIndex);
  }, [signals, currentPage, itemsPerPage]);

  const handlePageChange = (page) => {
    setCurrentPage(page);
    // Scroll to top when page changes
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    setCurrentPage(1); // Reset to first page when filters change
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error.message} />;
  }

  return (
    <div className="space-y-6">
      {/* Filter Controls */}
      <div className="bg-white p-4 rounded-lg shadow">
        {/* Add your filter components here */}
      </div>

      {/* Signals Table */}
      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {paginatedData.map((signal) => (
            <li key={signal.id} className="px-6 py-4">
              {/* Signal item content */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">
                    {signal.ticker}
                  </h3>
                  <p className="text-sm text-gray-500">
                    {signal.action} • {signal.strategy}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-semibold text-gray-900">
                    ${signal.entry_price}
                  </p>
                  <p className="text-sm text-gray-500">
                    {new Date(signal.timestamp).toLocaleDateString()}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Pagination */}
      <Pagination
        currentPage={currentPage}
        totalItems={signals.length}
        itemsPerPage={itemsPerPage}
        onPageChange={handlePageChange}
      />
    </div>
  );
};

export default SignalList;
```

### 7. Advanced Features

#### Virtual Scrolling for Large Datasets

```jsx
// src/components/VirtualizedSignalList.jsx
import React from 'react';
import { FixedSizeList as List } from 'react-window';
import { useSignals } from '../hooks/useSignals';

const SignalItem = ({ index, style, data }) => (
  <div style={style} className="border-b border-gray-200 px-6 py-4">
    <div className="flex items-center justify-between">
      <div>
        <h3 className="text-lg font-medium text-gray-900">
          {data[index].ticker}
        </h3>
        <p className="text-sm text-gray-500">
          {data[index].action} • {data[index].strategy}
        </p>
      </div>
      <div className="text-right">
        <p className="text-lg font-semibold text-gray-900">
          ${data[index].entry_price}
        </p>
      </div>
    </div>
  </div>
);

const VirtualizedSignalList = () => {
  const { data: signals = [], isLoading, error } = useSignals();

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <List
      height={600}
      itemCount={signals.length}
      itemSize={100}
      itemData={signals}
    >
      {SignalItem}
    </List>
  );
};

export default VirtualizedSignalList;
```

#### Infinite Scrolling

```jsx
// src/hooks/useInfiniteSignals.js
import { useInfiniteQuery } from '@tanstack/react-query';

export const useInfiniteSignals = (filters = {}) => {
  return useInfiniteQuery({
    queryKey: ['signals', 'infinite', filters],
    queryFn: ({ pageParam = 0 }) => {
      // Simulate pagination on fetched data
      const pageSize = 20;
      return signalService.getAllSignals(filters).then(data => ({
        data: data.slice(pageParam * pageSize, (pageParam + 1) * pageSize),
        nextPage: (pageParam + 1) * pageSize < data.length ? pageParam + 1 : undefined,
      }));
    },
    getNextPageParam: (lastPage) => lastPage.nextPage,
  });
};
```

## Performance Optimizations

### 1. Data Caching Strategy

```jsx
// src/config/queryClient.js
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes - consider data fresh
      cacheTime: 30 * 60 * 1000, // 30 minutes - keep in cache
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});
```

### 2. Search and Filter Debouncing

```jsx
// src/hooks/useDebounce.js
import { useState, useEffect } from 'react';

export const useDebounce = (value, delay) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

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

// Usage in component
const [searchTerm, setSearchTerm] = useState('');
const debouncedSearchTerm = useDebounce(searchTerm, 300);

const filteredSignals = useMemo(() => {
  if (!debouncedSearchTerm) return signals;
  return signals.filter(signal => 
    signal.ticker.toLowerCase().includes(debouncedSearchTerm.toLowerCase())
  );
}, [signals, debouncedSearchTerm]);
```

### 3. Memoization for Expensive Calculations

```jsx
import React, { useMemo } from 'react';

const SignalAnalytics = ({ signals }) => {
  const analytics = useMemo(() => {
    return {
      totalSignals: signals.length,
      buySignals: signals.filter(s => s.action === 'buy').length,
      sellSignals: signals.filter(s => s.action === 'sell').length,
      avgProbability: signals.reduce((sum, s) => sum + (s.probability || 0), 0) / signals.length,
    };
  }, [signals]);

  return (
    <div className="grid grid-cols-4 gap-4">
      {/* Analytics display */}
    </div>
  );
};
```

## Request/Response Patterns

### Successful Response Format

```json
[
  {
    "id": 1,
    "ticker": "AAPL",
    "action": "buy",
    "entry_price": 150.25,
    "stop_loss": 145.00,
    "take_profit": 160.00,
    "timestamp": "2024-01-15T10:30:00Z",
    "strategy": "PULLBACK",
    "probability": "75%"
  }
]
```

### Error Handling

```jsx
// src/components/ErrorBoundary.jsx
import React from 'react';
import { QueryErrorResetBoundary } from '@tanstack/react-query';
import { ErrorBoundary } from 'react-error-boundary';

const ErrorFallback = ({ error, resetErrorBoundary }) => (
  <div className="text-center py-12">
    <h2 className="text-lg font-semibold text-gray-900 mb-2">
      Something went wrong
    </h2>
    <p className="text-gray-600 mb-4">{error.message}</p>
    <button
      onClick={resetErrorBoundary}
      className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
    >
      Try again
    </button>
  </div>
);

const App = () => (
  <QueryErrorResetBoundary>
    {({ reset }) => (
      <ErrorBoundary
        FallbackComponent={ErrorFallback}
        onReset={reset}
      >
        {/* Your app components */}
      </ErrorBoundary>
    )}
  </QueryErrorResetBoundary>
);
```

## Testing

### 1. Unit Tests for Hooks

```jsx
// src/hooks/__tests__/useSignals.test.js
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSignals } from '../useSignals';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

test('useSignals returns data successfully', async () => {
  const { result } = renderHook(() => useSignals(), {
    wrapper: createWrapper(),
  });

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data).toBeDefined();
});
```

### 2. Integration Tests

```jsx
// src/components/__tests__/SignalList.test.js
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import SignalList from '../SignalList';

const mockSignals = [
  {
    id: 1,
    ticker: 'AAPL',
    action: 'buy',
    entry_price: 150.25,
    timestamp: '2024-01-15T10:30:00Z',
  },
];

jest.mock('../hooks/useSignals', () => ({
  useSignals: () => ({
    data: mockSignals,
    isLoading: false,
    error: null,
  }),
}));

test('renders signal list correctly', () => {
  const queryClient = new QueryClient();
  
  render(
    <QueryClientProvider client={queryClient}>
      <SignalList />
    </QueryClientProvider>
  );

  expect(screen.getByText('AAPL')).toBeInTheDocument();
  expect(screen.getByText('buy')).toBeInTheDocument();
});
```

## Migration Checklist

- [x] Remove pagination from backend API endpoints
- [x] Update response models to return arrays instead of paginated responses
- [x] Remove pagination parameters from API calls
- [ ] Install React Query in frontend project
- [ ] Set up QueryClient with appropriate configuration
- [ ] Create API service functions
- [ ] Implement custom hooks for data fetching
- [ ] Create pagination components for frontend
- [ ] Implement search and filtering
- [ ] Add error handling and loading states
- [ ] Write tests for new functionality
- [ ] Update documentation
- [ ] Performance testing with large datasets

## Benefits of This Approach

1. **Better User Experience**: Instant filtering and searching without API calls
2. **Improved Performance**: Data caching reduces unnecessary API requests
3. **Offline Capability**: Cached data available when offline
4. **Flexible Pagination**: Easy to implement different pagination strategies
5. **Real-time Updates**: Easy to implement with React Query's invalidation system

## Next Steps

1. Implement the frontend components using the examples above
2. Test with your actual data volumes
3. Consider implementing virtual scrolling for very large datasets
4. Add real-time updates using WebSocket integration with React Query
5. Implement advanced filtering and sorting capabilities