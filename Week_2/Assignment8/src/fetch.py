utf-8import requests

DEFAULT_USER_AGENT = (
    "SSRISS-WebMonitor/0.1 (educational scraping project; contact: saanvi@example.com)"
)


def fetch(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 10) -> tuple[str, int]:
    """
    Fetch a URL and return (html_text, http_status_code).
    Raises RuntimeError on network / HTTP failures.
    """
    headers = {"User-Agent": user_agent}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Request timed out: {url}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching {url}: {e}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}")

    return response.text, response.status_code
