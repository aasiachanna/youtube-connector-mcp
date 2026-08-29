#!/usr/bin/env python3
"""Simple non-streaming MCP JSON-RPC test client.

Sends a minimal JSON-RPC request to POST /mcp on localhost:8000
and prints the HTTP status and body. Safe and quick smoke test.
"""
import http.client
import json
import sys

HOST = "127.0.0.1"
PORT = 8000

def main():
    payload = {"jsonrpc": "2.0", "method": "ping", "id": 1}
    body = json.dumps(payload)

    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
    try:
        # Streamable HTTP transport requires the client to accept both
        # JSON and server-sent-events. Include both in the Accept header.
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        conn.request("POST", "/mcp", body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        print(f"HTTP {resp.status} {resp.reason}")
        try:
            parsed = json.loads(data)
            print(json.dumps(parsed, indent=2))
        except Exception:
            print(data.decode(errors="replace"))
    except Exception as e:
        print("Request failed:", e)
        sys.exit(2)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
