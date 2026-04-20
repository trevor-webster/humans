import argparse
import gzip
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zlib

DEFAULT_ISBN = "9780143122012"
DEFAULT_HOST = "z-library.im"
DEFAULT_ELEMENT = "z-bookcard"


def load_saved_headers(headers_path: Path) -> dict[str, str]:
    if not headers_path.exists():
        return {}

    lines = [line.strip() for line in headers_path.read_text(encoding="utf-8", errors="replace").splitlines()]
    pairs: dict[str, str] = {}
    for index in range(0, len(lines) - 1, 2):
        key = lines[index]
        value = lines[index + 1]
        if not key or key.startswith(":"):
            continue
        pairs[key.lower()] = value
    return pairs


def normalize_element_arg(value: str) -> str:
    return value.split("=", 1)[1] if value.startswith("element=") else value


def normalize_host_arg(value: str | None) -> str | None:
    if value is None:
        return None
    host = value.split("=", 1)[1] if value.startswith("host=") else value
    host = host.strip()
    if "://" in host:
        host = urllib.parse.urlparse(host).netloc or urllib.parse.urlparse(host).path
    return host.rstrip("/").split("/", 1)[0]


def is_named_arg(value: str | None) -> bool:
    return value is not None and "=" in value


def resolve_cli_value(
    positional: str | None,
    extras: dict[str, str],
    key: str,
    default: str,
) -> str:
    if key in extras:
        return extras[key]
    if positional is None:
        return default
    if positional.startswith(f"{key}="):
        return positional.split("=", 1)[1]
    if is_named_arg(positional):
        return default
    return positional


def parse_extra_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            continue
        key, item = value.split("=", 1)
        parsed[key] = item
    return parsed


def host_matches(cookie_domain: str, host: str) -> bool:
    domain = cookie_domain.lstrip(".").lower()
    host = host.lower()
    return host == domain or host.endswith(f".{domain}")


def load_cookie_header(cookie_path: Path, host: str) -> str | None:
    if not cookie_path.exists():
        return None

    cookies: list[str] = []
    for line in cookie_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        name, value, domain = parts[0], parts[1], parts[2]
        if host_matches(domain, host):
            cookies.append(f"{name}={value}")

    return "; ".join(cookies) if cookies else None


def build_request_headers(
    url: str,
    host: str | None,
    cookie_header: str | None,
) -> dict[str, str]:
    parsed_url = urllib.parse.urlparse(url)
    effective_host = host or parsed_url.hostname or DEFAULT_HOST
    saved_headers = load_saved_headers(Path(__file__).with_name("headers"))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    header_map = {
        "accept": "Accept",
        "accept-encoding": "Accept-Encoding",
        "accept-language": "Accept-Language",
        "cache-control": "Cache-Control",
        "priority": "Priority",
        "referer": "Referer",
        "sec-ch-ua": "Sec-CH-UA",
        "sec-ch-ua-mobile": "Sec-CH-UA-Mobile",
        "sec-ch-ua-platform": "Sec-CH-UA-Platform",
        "sec-fetch-dest": "Sec-Fetch-Dest",
        "sec-fetch-mode": "Sec-Fetch-Mode",
        "sec-fetch-site": "Sec-Fetch-Site",
        "upgrade-insecure-requests": "Upgrade-Insecure-Requests",
        "user-agent": "User-Agent",
    }
    for source_name, target_name in header_map.items():
        value = saved_headers.get(source_name)
        if value:
            headers[target_name] = value

    headers["Referer"] = f"https://{effective_host}{parsed_url.path or '/'}"
    headers["Origin"] = f"https://{effective_host}"
    headers["Host"] = effective_host

    saved_cookie = saved_headers.get("cookie")
    if saved_cookie:
        headers["Cookie"] = saved_cookie
    elif cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def fetch_html_with_curl(url: str, headers: dict[str, str]) -> str:
    command = [
        "curl.exe",
        "--silent",
        "--show-error",
        "--location",
        "--compressed",
        url,
    ]
    for key, value in headers.items():
        command.extend(["-H", f"{key}: {value}"])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise urllib.error.URLError(message) from exc
    return result.stdout


def decode_response_body(body: bytes, content_encoding: str | None, charset: str | None) -> str:
    encoding = (content_encoding or "").lower()
    if encoding == "gzip":
        body = gzip.decompress(body)
    elif encoding == "deflate":
        body = zlib.decompress(body)

    return body.decode(charset or "utf-8", errors="replace")


def fetch_html(url: str, host: str | None, cookie_header: str | None) -> str:
    headers = build_request_headers(url, host, cookie_header)
    try:
        return fetch_html_with_curl(url, headers)
    except urllib.error.URLError:
        pass

    urllib_headers = dict(headers)
    urllib_headers.pop("Accept-Encoding", None)
    request = urllib.request.Request(url, headers=urllib_headers)

    try:
        with urllib.request.urlopen(request) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            content_encoding = response.headers.get("Content-Encoding")
            return decode_response_body(response.read(), content_encoding, charset)
    except urllib.error.HTTPError:
        raise


def extract_first_id(html: str, element: str) -> str | None:
    pattern = re.compile(
        rf"<{re.escape(element)}\b[^>]*\bid=\"(\d{{7,10}})\"",
        re.IGNORECASE,
    )
    match = pattern.search(html)
    return match.group(1) if match else None


def fetch_story_html_for_host(url: str, host: str | None = None) -> str:
    cookie_path = Path(__file__).with_name("cookies")
    parsed_url = urllib.parse.urlparse(url)
    cookie_header = load_cookie_header(cookie_path, host or parsed_url.hostname or "")
    return fetch_html(url, host, cookie_header)


def dump_isbn_html(isbn: str, html: str) -> Path:
    output_path = Path.cwd() / f"{isbn}.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def get_story_bookcard_for_host(
    url: str,
    element: str,
    host: str | None = None,
) -> str | None:
    html = fetch_story_html_for_host(url, host)
    return extract_first_id(html, element)


def get_story_bookcard(url: str, element: str) -> str | None:
    return get_story_bookcard_for_host(url, element)


def build_isbn_url(isbn: str, host: str) -> str:
    return f"https://{host}/s/{isbn}"


def get_isbn_bookcard(
    isbn: str,
    host: str = DEFAULT_HOST,
    element: str = "z-bookcard",
) -> str | None:
    normalized_host = normalize_host_arg(host)
    if not normalized_host:
        normalized_host = DEFAULT_HOST

    url = build_isbn_url(isbn, normalized_host)
    html = fetch_story_html_for_host(url, normalized_host)
    dump_isbn_html(isbn, html)
    return extract_first_id(html, element)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch an ISBN page and print the first matching numeric id."
    )
    parser.add_argument(
        "isbn",
        nargs="?",
        help=f"ISBN to fetch (default: {DEFAULT_ISBN})",
    )
    parser.add_argument(
        "element",
        nargs="?",
        help=f"Element name to match (default: {DEFAULT_ELEMENT})",
    )
    parser.add_argument(
        "--host",
        help=f"Bare hostname only, no https:// (default: {DEFAULT_HOST}).",
    )
    args, extras = parser.parse_known_args()
    extra_args = parse_extra_args(extras)
    isbn = resolve_cli_value(
        args.isbn, extra_args, "isbn", DEFAULT_ISBN
    )
    element = normalize_element_arg(
        resolve_cli_value(args.element, extra_args, "element", DEFAULT_ELEMENT)
    )
    host = (
        normalize_host_arg(args.host)
        or normalize_host_arg(extra_args.get("host"))
        or DEFAULT_HOST
    )

    try:
        element_id = get_isbn_bookcard(isbn, host, element)
    except urllib.error.URLError as exc:
        print(f"Failed to fetch URL: {exc}", file=sys.stderr)
        return 1

    if element_id is None:
        print(
            f'No <{element}> element found with id matching "\\d{{7,10}}".',
            file=sys.stderr,
        )
        return 1

    print(element_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
