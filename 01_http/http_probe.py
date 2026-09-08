import sys
import requests
from requests.exceptions import RequestException

TIMEOUT_SECONDS = 10
DESCRIPTIVE_USER_AGENT = "web-monitor-internship/0.1 (educational probe; contact: your-email@example.com)"

HEADERS_OF_INTEREST = [
    "Content-Type",
    "Content-Length",
    "Server",
    "Date",
    "Cache-Control",
    "Location",
]


def probe(url: str) -> None:
    headers = {"User-Agent": DESCRIPTIVE_USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        print(f"[TIMEOUT] Request to {url} took longer than {TIMEOUT_SECONDS}s.")
        return
    except requests.exceptions.ConnectionError as exc:
        print(f"[CONNECTION ERROR] Could not connect to {url}.\nReason: {exc}")
        return
    except RequestException as exc:
        print(f"[REQUEST FAILED] {url}\nReason: {exc}")
        return

    content_type = response.headers.get("Content-Type", "")
    is_html = "text/html" in content_type.lower()

    print("=" * 60)
    print(f"requested_url:        {url}")
    print(f"final_url:            {response.url}")
    print(f"status_code:          {response.status_code}")
    print(f"content_type:         {content_type or '(none given)'}")
    print(f"content_length:       {len(response.content)} bytes")
    print(f"is_html_response:     {is_html}")

    print("\nredirect_history:")
    if response.history:
        for i, hop in enumerate(response.history, start=1):
            print(f"  {i}. {hop.status_code} -> {hop.url}")
    else:
        print("  (no redirects)")

    print("\nselected_response_headers:")
    for h in HEADERS_OF_INTEREST:
        if h in response.headers:
            print(f"  {h}: {response.headers[h]}")

    print("\nfirst_200_characters_of_body:")
    snippet = response.text[:200].replace("\n", "\\n")
    print(f"  {snippet!r}")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python http_probe.py <url>")
        sys.exit(1)

    probe(sys.argv[1])
