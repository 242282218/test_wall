"use client";

import type { ReactNode } from "react";
import { SWRConfig } from "swr";

export function SWRProvider({ children }: { children: ReactNode }) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        dedupingInterval: 30000,
        errorRetryCount: 2,
        onErrorRetry: (_error, _key, _config, revalidate, { retryCount }) => {
          if (retryCount >= 2) return;
          setTimeout(() => revalidate({ retryCount }), 1500);
        }
      }}
    >
      {children}
    </SWRConfig>
  );
}