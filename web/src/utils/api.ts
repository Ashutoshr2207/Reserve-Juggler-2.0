export class ApiError extends Error {
  public readonly status: number;
  public readonly endpoint: string;
  public readonly isNetworkError: boolean;
  public readonly responseBody?: string;

  constructor(
    message: string,
    status: number = 0,
    endpoint: string = '',
    responseBody?: string
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.endpoint = endpoint;
    this.isNetworkError = status === 0;
    this.responseBody = responseBody;
  }
}

let activeCsrfToken = '';

export function setCsrfToken(token: string) {
  activeCsrfToken = token;
}

export function getCsrfToken(): string {
  return activeCsrfToken;
}

export async function api<T>(path: string, payload?: unknown): Promise<T> {
  const url = `/api/${path}`;
  let response: Response;

  const headers: Record<string, string> = {};
  if (payload !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (activeCsrfToken) {
    headers['X-CSRF-Token'] = activeCsrfToken;
  }

  try {
    response = await fetch(
      url,
      payload === undefined
        ? {
            credentials: 'include',
            headers,
            signal: AbortSignal.timeout(120000)
          }
        : {
            method: 'POST',
            credentials: 'include',
            headers,
            body: JSON.stringify(payload),
            signal: AbortSignal.timeout(120000)
          }
    );
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'TimeoutError') {
      throw new ApiError(`Request to ${url} timed out after 120s.`, 408, path);
    }
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(
      `Unable to connect to the Reserve Juggler server (${message}). Verify the backend process is running on port 8000.`,
      0,
      path
    );
  }

  // Read response as text first to safely handle empty bodies, HTML, or malformed responses
  let rawText = '';
  try {
    rawText = await response.text();
  } catch (readErr: unknown) {
    throw new ApiError(
      `Failed to read response from ${url} (HTTP ${response.status}): ${readErr instanceof Error ? readErr.message : String(readErr)}`,
      response.status,
      path
    );
  }

  const trimmed = rawText.trim();
  let parsed: unknown = null;
  let isJson = false;

  if (trimmed.length > 0) {
    try {
      parsed = JSON.parse(trimmed);
      isJson = true;
    } catch {
      isJson = false;
    }
  }

  // Handle non-OK HTTP status codes
  if (!response.ok) {
    let detail = '';
    if (isJson && parsed && typeof parsed === 'object') {
      const errorObj = parsed as Record<string, unknown>;
      if (typeof errorObj.error === 'string') {
        detail = errorObj.error;
      }
    }

    if (!detail) {
      if (trimmed.length > 0 && trimmed.length < 200) {
        detail = trimmed;
      } else {
        detail = response.statusText || 'Server Error';
      }
    }

    throw new ApiError(
      `Request to ${url} failed (${response.status}): ${detail}`,
      response.status,
      path,
      trimmed
    );
  }

  // Successful HTTP status (2xx), but empty response body
  if (trimmed.length === 0) {
    throw new ApiError(
      `Server returned an empty response (${response.status}) for ${url}. Expected JSON data.`,
      response.status,
      path
    );
  }

  // Successful HTTP status (2xx), but body was not valid JSON
  if (!isJson) {
    const preview = trimmed.slice(0, 100);
    throw new ApiError(
      `Invalid non-JSON response from ${url} (${response.status}): ${preview}`,
      response.status,
      path,
      trimmed
    );
  }

  return parsed as T;
}

