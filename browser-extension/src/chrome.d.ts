declare const chrome: {
  runtime: {
    onInstalled: {
      addListener(callback: () => void): void;
    };
    sendMessage(message: unknown, callback?: (response?: unknown) => void): void;
    onMessage: {
      addListener(
        callback: (
          message: unknown,
          sender: { tab?: { id?: number; url?: string } },
          sendResponse: (response?: unknown) => void
        ) => boolean | void
      ): void;
    };
    lastError?: { message?: string };
  };
  tabs: {
    create(
      createProperties: { url: string; active?: boolean },
      callback?: (tab: { id?: number; url?: string; status?: string }) => void
    ): void;
    get(
      tabId: number,
      callback: (tab: { id?: number; url?: string; status?: string }) => void
    ): void;
    query(
      queryInfo: { url?: string | string[]; active?: boolean; currentWindow?: boolean },
      callback: (tabs: Array<{ id?: number; url?: string; status?: string }>) => void
    ): void;
    update(tabId: number, updateProperties: { url?: string; active?: boolean }, callback?: () => void): void;
    sendMessage(tabId: number, message: unknown, callback?: (response?: unknown) => void): void;
    remove(tabId: number, callback?: () => void): void;
  };
};
