import { vi } from "vitest";

export function mockJsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

export function getFetchCall(index = 0): { url: string; options: RequestInit } {
  const call = vi.mocked(fetch).mock.calls[index];
  if (call === undefined || typeof call[0] !== "string" || call[1] === undefined) {
    throw new TypeError(`Missing fetch call ${index}`);
  }

  return { url: call[0], options: call[1] };
}
