"""Raster -> SVG vectorization, provider-switchable.

Two built-in providers:

  recraft (default) - Recraft API's vectorize endpoint. Costs 10 API units
    (= $0.01) per call. Input: PNG/JPG/WEBP, <=10MB, <=16MP, max dimension
    4096px, MIN dimension 256px. Requires an API key (see resolution order
    below). The key is never printed.

  vtracer - the local `vtracer` Python package. Free, no API key, no
    network call. Output quality differs from Recraft's but downstream
    svg_normalize.py / qc_svg.py clean and gate the result either way.

Provider resolution order (first match wins):
  1. --provider command-line argument
  2. OPENILLUST_VECTORIZER environment variable
  3. tooling.vectorizer in the campaign file, if --campaign was given
     (campaign.py is imported lazily, only when --campaign is present; a
     campaign file without a tooling.vectorizer key is treated as having
     no opinion and falls through)
  4. default: "recraft"

An unknown resolved provider name is a hard error naming the valid choices.

Usage:
  python vectorize.py --input ref.png --output out.svg
  python vectorize.py --input ref.png --output out.svg --provider vtracer
  python vectorize.py --input ref.png --output out.svg --campaign campaign.yaml
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ENDPOINT = "https://external.api.recraft.ai/v1/images/vectorize"

INPUT_CONTENT_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def find_env():
    """.env lives in the campaign project, not next to the (installable) skill:
    walk up from the current working directory."""
    d = Path.cwd()
    for candidate in [d, *d.parents]:
        if (candidate / ".env").exists():
            return candidate / ".env"
    return None


def load_key(cli_key):
    if cli_key:
        return cli_key
    if os.environ.get("RECRAFT_API_KEY"):
        return os.environ["RECRAFT_API_KEY"]
    env = find_env()
    if env:
        lines = [ln.strip() for ln in env.read_text(encoding="utf-8-sig").splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
        for line in lines:
            if line.startswith("RECRAFT_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
        # tolerate a bare-key .env (a single line holding just the key value)
        if len(lines) == 1 and "=" not in lines[0]:
            return lines[0]
    sys.exit("no API key: pass --key, set RECRAFT_API_KEY, or put "
             "RECRAFT_API_KEY=... in .env at the repo root")


def multipart(field, filename, data, content_type):
    boundary = "----openillust-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def vectorize_recraft(args):
    src = Path(args.input)
    ext = src.suffix.lower().lstrip(".")
    ctype = INPUT_CONTENT_TYPES.get(ext)
    if not ctype:
        sys.exit(f"unsupported input type: {src.suffix}")
    data = src.read_bytes()
    if len(data) > 10 * 1024 * 1024:
        sys.exit("input exceeds the 10MB API limit")

    key = load_key(args.key)
    body, content_type = multipart("file", src.name, data, ctype)
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        sys.exit(f"API error {e.code}: {detail}")

    image = payload.get("image", {})
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if image.get("url"):
        with urllib.request.urlopen(image["url"], timeout=120) as r:
            out.write_bytes(r.read())
    elif image.get("b64_json"):
        import base64
        out.write_bytes(base64.b64decode(image["b64_json"]))
    else:
        sys.exit(f"unexpected response shape: {json.dumps(payload)[:300]}")
    print(f"wrote {out} ({out.stat().st_size} bytes); cost: 10 API units ($0.01)")


def vectorize_vtracer(args):
    src = Path(args.input)
    ext = src.suffix.lower().lstrip(".")
    if ext not in INPUT_CONTENT_TYPES:
        sys.exit(f"unsupported input type: {src.suffix}")

    import vtracer

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    vtracer.convert_image_to_svg_py(str(src), str(out), colormode="color", mode="spline")
    print(f"wrote {out} ({out.stat().st_size} bytes); cost: $0 (local vtracer)")


PROVIDERS = {
    "recraft": vectorize_recraft,
    "vtracer": vectorize_vtracer,
}


def resolve_provider(args):
    if args.provider:
        return args.provider
    if os.environ.get("OPENILLUST_VECTORIZER"):
        return os.environ["OPENILLUST_VECTORIZER"]
    if args.campaign:
        from campaign import load_campaign  # lazy: keep the no-campaign path PyYAML-free
        campaign = load_campaign(args.campaign)
        vectorizer = (campaign.get("tooling") or {}).get("vectorizer")
        if vectorizer:
            return vectorizer
    return "recraft"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default=None,
                     help="vectorizer provider (default: resolved from env/campaign/'recraft')")
    ap.add_argument("--campaign", help="path to campaign.yaml (consulted for tooling.vectorizer)")
    ap.add_argument("--key", help="Recraft API key (prefer .env instead)")
    args = ap.parse_args()

    provider = resolve_provider(args)
    adapter = PROVIDERS.get(provider)
    if adapter is None:
        sys.exit(f"unknown provider {provider!r}: valid providers are {sorted(PROVIDERS)}")
    adapter(args)


if __name__ == "__main__":
    main()
