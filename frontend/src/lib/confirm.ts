export type ConfirmOptions = {
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "primary" | "danger";
};
export type ConfirmRequest = ConfirmOptions & {
  message: string;
  resolve: (value: boolean) => void;
};

const hosts = new Set<(request: ConfirmRequest) => void>();

export function registerConfirmHost(host: (request: ConfirmRequest) => void): () => void {
  hosts.add(host);
  return () => {
    hosts.delete(host);
  };
}

/**
 * Asks the user to confirm an action with the app's own dialog.
 * Falls back to the browser dialog only when no ConfirmHost is mounted
 * (isolated component tests).
 */
export function confirmAction(message: string, options: ConfirmOptions = {}): Promise<boolean> {
  if (hosts.size === 0) return Promise.resolve(window.confirm(message));
  return new Promise(resolve => {
    const [host] = hosts;
    host({ ...options, message, resolve });
  });
}
