#!/usr/bin/env python3
"""
Automatically extract Leonteq API token from browser session.

This script opens a browser, lets you log in to Leonteq, then automatically
captures the JWT Bearer token from the API requests and saves it to .env file.

Usage:
    python scripts/get_leonteq_token.py
"""

import sys
import time
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def extract_token_interactive(timeout_ms: int = 300000) -> str:
    """
    Open browser, wait for user to navigate to Leonteq site, capture API token.

    Args:
        timeout_ms: Maximum time to wait (default: 5 minutes)

    Returns:
        JWT Bearer token string

    Raises:
        RuntimeError: If timeout or Playwright not available
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("Playwright not available. Install with: poetry install") from exc

    print("=" * 80)
    print("Leonteq API Token Extraction")
    print("=" * 80)
    print()
    print("This script will:")
    print("1. Open a browser to Leonteq website")
    print("2. Wait for you to browse/interact with the site")
    print("3. Automatically capture the API token from network requests")
    print("4. Save the token to your .env file")
    print()
    print("Instructions:")
    print("- The browser will open to structuredproducts-ch.leonteq.com")
    print("- Navigate around the site (browse products, etc.)")
    print("- The script will automatically detect API calls")
    print("- Once detected, the browser will close automatically")
    print()
    print(f"Timeout: {timeout_ms / 1000:.0f} seconds")
    print()
    input("Press ENTER to open browser...")

    captured_token = None

    def handle_request(request):
        """Capture Authorization header from API requests."""
        nonlocal captured_token

        # Look for API requests to /rfb-api/products
        if "/rfb-api/products" in request.url:
            headers = request.headers
            auth_header = headers.get("authorization") or headers.get("Authorization")

            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "").strip()
                if token and len(token) > 100:  # JWT tokens are long
                    captured_token = token
                    print(f"\n✓ Token captured! (length: {len(token)} chars)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Listen to all requests
        page.on("request", handle_request)

        # Navigate to Leonteq
        print("\nOpening Leonteq website...")
        page.goto("https://structuredproducts-ch.leonteq.com", wait_until="domcontentloaded", timeout=timeout_ms)

        deadline = time.time() + (timeout_ms / 1000)
        start_time = time.time()

        print("\nWaiting for API token...")
        print("(Browse the site normally - the script will detect API calls automatically)")
        print()

        # Wait for token to be captured
        while time.time() < deadline:
            elapsed = time.time() - start_time

            if captured_token:
                # Wait a bit to ensure we have the token
                time.sleep(1)
                print(f"\n✓ Token extraction successful after {elapsed:.1f} seconds!")
                break

            # Check every second
            page.wait_for_timeout(1000)

            # Print status every 10 seconds
            if int(elapsed) % 10 == 0 and elapsed > 0:
                print(f"  Still waiting... ({elapsed:.0f}s elapsed)")

        context.close()
        browser.close()

    if not captured_token:
        raise RuntimeError("Token extraction timed out. No API requests detected.")

    return captured_token


def update_env_file(token: str) -> None:
    """
    Update .env file with the captured token.

    Args:
        token: JWT Bearer token to save
    """
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        # Create from example
        env_example = Path(__file__).parent.parent / ".env.example"
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_path)
            print(f"\n✓ Created .env file from .env.example")
        else:
            raise RuntimeError(".env file not found and .env.example doesn't exist")

    # Read current content
    content = env_path.read_text()

    # Update or add token
    token_pattern = r'^SPA_LEONTEQ_API_TOKEN=.*$'
    token_line = f'SPA_LEONTEQ_API_TOKEN={token}'

    if re.search(token_pattern, content, re.MULTILINE):
        # Replace existing token
        new_content = re.sub(token_pattern, token_line, content, flags=re.MULTILINE)
        print(f"\n✓ Updated existing SPA_LEONTEQ_API_TOKEN in .env")
    else:
        # Add token at the end
        if not content.endswith('\n'):
            content += '\n'
        new_content = content + f'\n{token_line}\n'
        print(f"\n✓ Added SPA_LEONTEQ_API_TOKEN to .env")

    # Write back
    env_path.write_text(new_content)


def verify_token(token: str) -> bool:
    """
    Verify the token works by making a test API request.

    Args:
        token: JWT Bearer token to test

    Returns:
        True if token is valid, False otherwise
    """
    print("\n" + "=" * 80)
    print("Verifying Token")
    print("=" * 80)

    try:
        from core.sources.leonteq_api import fetch_products_page

        print("\nTesting API connection with captured token...")
        response = fetch_products_page(token, offset=0, page_size=1)

        total = response.get("searchMetadata", {}).get("totalHits", 0)
        products = response.get("products", [])

        print(f"\n✓ Token is valid!")
        print(f"  Total products available: {total:,}")
        print(f"  Test fetch returned: {len(products)} product(s)")

        if products:
            product = products[0]
            isin = product.get("identifiers", {}).get("isin", "unknown")
            print(f"  Sample ISIN: {isin}")

        return True

    except Exception as e:
        print(f"\n✗ Token verification failed: {e}")
        return False


def main():
    """Main entry point."""
    try:
        # Extract token
        print()
        token = extract_token_interactive()

        # Show token preview
        print("\n" + "=" * 80)
        print("Token Captured")
        print("=" * 80)
        print(f"\nToken preview: {token[:50]}...{token[-20:]}")
        print(f"Token length: {len(token)} characters")

        # Update .env file
        update_env_file(token)

        # Verify token works
        if verify_token(token):
            print("\n" + "=" * 80)
            print("✓ Success!")
            print("=" * 80)
            print("\nYour Leonteq API token has been saved to .env file.")
            print("\nNext steps:")
            print("1. Run the test script: python3 scripts/test_leonteq_api.py")
            print("2. Or start the crawler: POST /api/ingest/crawl/leonteq-api")
            print("3. Monitor progress: http://localhost:8000/static/status.html")
            print()
            return 0
        else:
            print("\n✗ Token verification failed. The token may be invalid.")
            print("Try running the script again.")
            return 1

    except KeyboardInterrupt:
        print("\n\n✗ Cancelled by user")
        return 1
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
