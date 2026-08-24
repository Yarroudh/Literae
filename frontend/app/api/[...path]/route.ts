import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const allowedPaths = /^(chat(?:\/stream)?|conversations(?:\/[^/]+)?)$/;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const targetPath = path.join("/");
  if (!allowedPaths.test(targetPath)) {
    return Response.json({ detail: "Not found." }, { status: 404 });
  }

  const apiUrl = process.env.API_INTERNAL_URL;
  const apiKey = process.env.INTERNAL_API_KEY;
  if (!apiUrl || !apiKey) {
    return Response.json({ detail: "The research service is unavailable." }, { status: 503 });
  }

  const headers = new Headers();
  headers.set("x-internal-api-key", apiKey);
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);

  const upstream = await fetch(`${apiUrl.replace(/\/$/, "")}/${targetPath}`, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    signal: request.signal,
    redirect: "manual",
    duplex: "half",
  } as RequestInit & { duplex: "half" });

  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType) responseHeaders.set("content-type", upstreamContentType);
  responseHeaders.set("cache-control", "no-store");
  if (upstream.headers.get("x-accel-buffering")) {
    responseHeaders.set("x-accel-buffering", "no");
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
