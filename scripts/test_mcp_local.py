#!/usr/bin/env python3
"""
Test script for MCP server in remote mode locally.

This script simulates what Claude.ai does:
1. Fetches OAuth metadata
2. Registers a client
3. Gets authorization code
4. Exchanges code for token
5. Connects to /mcp endpoint

Usage:
    # Terminal 1: Start the server
    export SERVICE_NOTION_TOKEN=your_token
    export SERVICE_ASANA_TOKEN=your_token
    export DEFAULT_USER_EMAIL=test@example.com
    python -m notion_dev.mcp_server.server --transport sse --port 8000

    # Terminal 2: Run the test
    python scripts/test_mcp_local.py
"""

import httpx
import json
import sys
import time

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("\n=== Testing /health ===")
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_oauth_metadata():
    """Test OAuth metadata endpoint."""
    print("\n=== Testing /.well-known/oauth-authorization-server ===")
    try:
        r = httpx.get(f"{BASE_URL}/.well-known/oauth-authorization-server", timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_protected_resource():
    """Test protected resource metadata endpoint."""
    print("\n=== Testing /.well-known/oauth-protected-resource ===")
    try:
        r = httpx.get(f"{BASE_URL}/.well-known/oauth-protected-resource", timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_client_registration():
    """Test dynamic client registration."""
    print("\n=== Testing /register ===")
    try:
        r = httpx.post(
            f"{BASE_URL}/register",
            json={
                "client_name": "Test Client",
                "redirect_uris": ["http://localhost:3000/callback"],
            },
            timeout=5,
        )
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        if r.status_code == 201:
            return r.json().get("client_id")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_authorization(client_id: str):
    """Test authorization endpoint (no-auth mode should redirect immediately)."""
    print("\n=== Testing /authorize ===")
    try:
        r = httpx.get(
            f"{BASE_URL}/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "http://localhost:3000/callback",
                "code_challenge": "test_challenge_1234567890123456789012345678901234567890123",
                "code_challenge_method": "S256",
                "state": "test_state",
                "scope": "mcp:tools",
            },
            follow_redirects=False,
            timeout=5,
        )
        print(f"Status: {r.status_code}")
        print(f"Location: {r.headers.get('location', 'N/A')}")

        if r.status_code == 302:
            location = r.headers.get("location", "")
            # Extract code from redirect URL
            if "code=" in location:
                code = location.split("code=")[1].split("&")[0]
                print(f"Authorization code: {code}")
                return code
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_token_exchange(client_id: str, code: str):
    """Test token exchange."""
    print("\n=== Testing /token ===")
    try:
        r = httpx.post(
            f"{BASE_URL}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "http://localhost:3000/callback",
                "client_id": client_id,
                "code_verifier": "test_verifier",
            },
            timeout=5,
        )
        print(f"Status: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2)}")
        if r.status_code == 200:
            return r.json().get("access_token")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_mcp_endpoint(access_token: str = None):
    """Test MCP endpoint with POST (Streamable HTTP)."""
    print("\n=== Testing POST /mcp ===")

    # Important: MCP requires both application/json AND text/event-stream in Accept header
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    # Send a JSON-RPC initialize request
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    try:
        r = httpx.post(
            f"{BASE_URL}/mcp",
            json=payload,
            headers=headers,
            timeout=10,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type', 'N/A')}")

        if r.status_code == 200:
            content_type = r.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                print("Response (SSE stream):")
                print(r.text[:500] + "..." if len(r.text) > 500 else r.text)
            else:
                print(f"Response: {json.dumps(r.json(), indent=2)}")
            return True
        else:
            print(f"Response: {r.text[:500]}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_sse_endpoint():
    """Test SSE endpoint (deprecated but should still work)."""
    print("\n=== Testing POST /sse ===")

    try:
        r = httpx.post(
            f"{BASE_URL}/sse",
            timeout=5,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type', 'N/A')}")
        # SSE returns 200 with streaming, we just check it doesn't error
        return r.status_code == 200
    except httpx.ReadTimeout:
        # Expected for SSE - it streams indefinitely
        print("SSE connection opened (timeout expected)")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    print("=" * 60)
    print("MCP Server Local Test")
    print("=" * 60)
    print(f"Testing server at: {BASE_URL}")

    results = {}

    # Test health
    results["health"] = test_health()

    # Test OAuth metadata
    results["oauth_metadata"] = test_oauth_metadata()
    results["protected_resource"] = test_protected_resource()

    # Test client registration
    client_id = test_client_registration()
    results["registration"] = client_id is not None

    if client_id:
        # Test authorization
        code = test_authorization(client_id)
        results["authorization"] = code is not None

        if code:
            # Test token exchange
            token = test_token_exchange(client_id, code)
            results["token"] = token is not None

            # Test MCP endpoint with token
            results["mcp_with_token"] = test_mcp_endpoint(token)

    # Test MCP endpoint without token (no-auth mode)
    results["mcp_no_token"] = test_mcp_endpoint()

    # Test SSE endpoint
    results["sse"] = test_sse_endpoint()

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("All tests passed! ✅")
        return 0
    else:
        print("Some tests failed! ❌")
        return 1


if __name__ == "__main__":
    sys.exit(main())
