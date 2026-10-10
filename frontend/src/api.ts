export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', ...options });
  const data = await response.json().catch(() => null);
  if (options.signal?.aborted) throw new DOMException('Request aborted', 'AbortError');
  if (!response.ok) {
    // Clear the photo interface when a session expires, including in another tab.
    if (response.status === 401 && path !== '/api/login/') {
      window.dispatchEvent(new Event('session-expired'));
    }
    const message = data?.error || (response.status === 403
      ? 'Your session changed. Refresh the page and try again.'
      : 'The request failed. Please try again.');
    throw new ApiError(message, response.status);
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}
