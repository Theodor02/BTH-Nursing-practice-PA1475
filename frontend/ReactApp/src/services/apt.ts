export async function getHello() {
  const res = await fetch("/api/");
  return res.json();
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(path, { credentials: "include", ...init }).then((response) => {
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("session-expired"));
    }
    return response;
  });
}