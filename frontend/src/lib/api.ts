const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private baseUrl: string;
  private refreshing: Promise<boolean> | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = { "Content-Type": "application/json" };
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  /** Try to refresh the access token using the stored refresh_token. */
  private async tryRefresh(): Promise<boolean> {
    if (typeof window === "undefined") return false;
    // Deduplicate concurrent refresh attempts
    if (this.refreshing) return this.refreshing;

    this.refreshing = (async () => {
      const refreshToken = localStorage.getItem("refresh_token");
      if (!refreshToken) return false;
      try {
        const res = await fetch(`${this.baseUrl}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          return false;
        }
        const data: { access_token: string; refresh_token: string } = await res.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        return true;
      } catch {
        return false;
      }
    })();

    const result = await this.refreshing;
    this.refreshing = null;
    return result;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    retry = true,
  ): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: this.getHeaders(),
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401 && retry) {
      const refreshed = await this.tryRefresh();
      if (refreshed) return this.request<T>(method, path, body, false);
      // Refresh failed — redirect to login
      if (typeof window !== "undefined") window.location.href = "/auth/login";
      throw new Error("Session expired");
    }

    if (!res.ok) {
      let detail = `${method} ${path} failed: ${res.status}`;
      try {
        const errBody = await res.json();
        if (errBody?.error) detail = errBody.error;
        else if (errBody?.detail) detail = typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail);
      } catch { /* ignore parse error */ }
      throw new Error(detail);
    }
    return res.json();
  }

  async get<T = unknown>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  async post<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  async put<T = unknown>(path: string, body: unknown): Promise<T> {
    return this.request<T>("PUT", path, body);
  }

  async patch<T = unknown>(path: string, body: unknown): Promise<T> {
    return this.request<T>("PATCH", path, body);
  }

  async delete<T = unknown>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }

  async postFormData<T = unknown>(path: string, formData: FormData): Promise<T> {
    const headers: HeadersInit = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (res.status === 401) {
      const refreshed = await this.tryRefresh();
      if (refreshed) return this.postFormData<T>(path, formData);
      if (typeof window !== "undefined") window.location.href = "/auth/login";
      throw new Error("Session expired");
    }
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
    return res.json();
  }
}

export const api = new ApiClient(API_BASE);
