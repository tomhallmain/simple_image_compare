"""
Generate a standalone HTML page to verify browser-extension image classification side effects.

The page loads a target <img> and watches for typical extension behaviors: style/class
mutations, computed-style hiding (display/visibility/opacity/size), or removal of the
img from the DOM. When a change is detected, a status region is updated (positive signal).

Without ``--serve``, the image is not copied: ``src`` uses a ``file:`` URL.

With ``--serve`` (default layout), a **session folder** is created next to Weidr logs
(``%APPDATA%/Weidr/classifier_probe/`` on Windows, ``~/.local/share/Weidr/classifier_probe/``
elsewhere), the image is **copied** there once, the HTML is written beside it, and both
are served from ``http://127.0.0.1`` so you avoid ``file:`` origin issues and never touch
the git tree. The session folder is removed when you press Enter unless ``--keep-session``.

Use ``--serve-in-place`` to skip the copy and use the old “common parent of image + output”
layout (e.g. same drive as the repo).

Usage:
  python tests/generate_browser_classifier_test_page.py
  python tests/generate_browser_classifier_test_page.py --image C:/path/to/sample.jpg
  python tests/generate_browser_classifier_test_page.py --image ./photo.png --serve
  python tests/generate_browser_classifier_test_page.py --image D:/pics/x.jpg --serve-in-place --output D:/pics/probe.html --serve

With ``--serve``, open the printed ``http://127.0.0.1:...`` URL in the browser (not file://).
"""

from __future__ import annotations

import argparse
import functools
import html
import http.server
import os
import shutil
import socket
import socketserver
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path


# Tiny 1x1 PNG (red) used when --image is omitted so the page always has a valid src.
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Classifier extension probe</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 52rem; }}
    #detection-status {{
      margin-top: 1rem; padding: 0.75rem 1rem; border: 1px solid #888;
      border-radius: 6px; background: #f4f4f4;
    }}
    #detection-status.positive {{
      background: #d4edda; border-color: #28a745; font-weight: 600;
    }}
    #probe-wrap {{ margin-top: 1rem; }}
    img#test-img {{ max-width: 100%; height: auto; vertical-align: middle; }}
    .hint {{ color: #555; font-size: 0.9rem; }}
    code {{ background: #eee; padding: 0.1em 0.35em; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>Browser classifier extension test</h1>
  <p class="hint">
    This page loads a single image (<code>id=&quot;test-img&quot;</code>). If an extension
    modifies or removes that node after load, the status below should flip to a positive result.
    <!-- TODO: tune selectors or add extension-specific hooks if your extension targets different markup. -->
  </p>
  <div id="probe-wrap">
    <img id="test-img" src="{img_src}" alt="classification probe"{img_dims} />
  </div>
  <div id="detection-status" aria-live="polite">Watching… no extension interference detected yet.</div>
  <p class="hint">Baseline is captured after the image <code>load</code> event (and again on window <code>load</code>).</p>
  <script>
(function () {{
  const banner = document.getElementById('detection-status');
  const imgId = 'test-img';
  let reported = false;
  let baseline = null;

  function report(reason) {{
    if (reported) return;
    reported = true;
    banner.textContent = 'Positive result: ' + reason;
    banner.className = 'positive';
  }}

  function snapshot(el) {{
    if (!el || !el.isConnected) return null;
    const cs = window.getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {{
      styleAttr: el.getAttribute('style') || '',
      className: el.className || '',
      display: cs.display,
      visibility: cs.visibility,
      opacity: cs.opacity,
      filter: cs.filter,
      width: r.width,
      height: r.height,
      inDocument: document.documentElement.contains(el),
    }};
  }}

  function armBaseline(el) {{
    baseline = snapshot(el);
  }}

  function check() {{
    const el = document.getElementById(imgId);
    if (!el || !document.documentElement.contains(el)) {{
      report('img element is missing or no longer in the document.');
      return;
    }}
    if (!baseline) return;
    const now = snapshot(el);
    if (!now) {{
      report('img snapshot failed (element not connected).');
      return;
    }}
    if (now.styleAttr !== baseline.styleAttr) {{
      report('img style attribute changed.');
      return;
    }}
    if (now.className !== baseline.className) {{
      report('img class attribute changed.');
      return;
    }}
    if (now.display !== baseline.display) {{
      report('computed display changed (' + baseline.display + ' -> ' + now.display + ').');
      return;
    }}
    if (now.visibility !== baseline.visibility) {{
      report('computed visibility changed.');
      return;
    }}
    if (now.opacity !== baseline.opacity) {{
      report('computed opacity changed.');
      return;
    }}
    if (now.filter !== baseline.filter) {{
      report('computed filter changed.');
      return;
    }}
    if (now.width < 0.5 && now.height < 0.5 && (baseline.width >= 0.5 || baseline.height >= 0.5)) {{
      report('img layout size collapsed to near zero.');
      return;
    }}
  }}

  const observer = new MutationObserver(function () {{ check(); }});
  observer.observe(document.body, {{
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['style', 'class', 'src', 'width', 'height'],
  }});

  let pollStarted = false;
  function startWatchers(firstEl) {{
    if (!firstEl) return;
    armBaseline(firstEl);
    observer.observe(firstEl, {{
      attributes: true,
      attributeFilter: ['style', 'class', 'src', 'width', 'height'],
    }});
    if (!pollStarted) {{
      pollStarted = true;
      window.setInterval(check, 300);
    }}
  }}

  const imgEl = document.getElementById(imgId);
  if (imgEl && imgEl.complete && imgEl.naturalWidth) {{
    startWatchers(imgEl);
  }} else if (imgEl) {{
    imgEl.addEventListener('load', function onImgLoad() {{
      imgEl.removeEventListener('load', onImgLoad);
      startWatchers(imgEl);
    }}, {{ once: true }});
    imgEl.addEventListener('error', function () {{
      report('img failed to load (network or bad src).');
    }}, {{ once: true }});
  }}

  window.addEventListener('load', function () {{
    const el = document.getElementById(imgId);
    if (!reported && el) {{
      armBaseline(el);
    }}
  }});
}})();
  </script>
</body>
</html>
"""


def _url_path_under_root(path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    parts = rel.as_posix().split("/")
    return "/".join(urllib.parse.quote(p, safe="") for p in parts)


def _probe_sessions_parent() -> Path:
    """Same app-data convention as ``utils/logging_setup.py`` (Weidr under APPDATA / .local/share)."""
    base = os.getenv("APPDATA") if sys.platform == "win32" else os.path.expanduser("~/.local/share")
    p = Path(base) / "Weidr" / "classifier_probe"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _resolve_serve_root(image: Path, output: Path, serve_root: Path | None) -> Path:
    if serve_root is not None:
        root = serve_root.resolve()
    else:
        try:
            root = Path(os.path.commonpath([str(image.resolve().parent), str(output.resolve().parent)]))
        except ValueError as e:
            raise SystemExit(
                "Could not derive a common folder for --serve (different drives?). "
                "Pass --serve-root DIR where DIR is a parent of both the image and the HTML file."
            ) from e
    img_r = image.resolve()
    out_r = output.resolve()
    try:
        img_r.relative_to(root)
        out_r.relative_to(root)
    except ValueError:
        raise SystemExit(
            f"--serve requires the image ({img_r}) and HTML output ({out_r}) to sit under "
            f"the serve root ({root}). Move the files or pass --serve-root."
        )
    return root


def _pick_listen_port(requested: int) -> int:
    if requested != 0:
        return requested
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _build_img_src(
    image: Path | None,
    *,
    serve: bool,
    serve_root: Path | None,
    http_image_path: Path | None,
    port: int | None,
) -> tuple[str, str]:
    """Return (escaped src for HTML attribute, extra img attribute fragment)."""
    if image is None:
        data_uri = "data:image/png;base64," + _TINY_PNG_B64
        return html.escape(data_uri, quote=True), ' width="1" height="1"'

    img_path = image.resolve()
    if not img_path.is_file():
        raise SystemExit(f"Image not found: {img_path}")

    if serve:
        if port is None or serve_root is None or http_image_path is None:
            raise SystemExit("internal error: incomplete serve paths for img src")
        rel = _url_path_under_root(http_image_path.resolve(), serve_root.resolve())
        url = f"http://127.0.0.1:{port}/{rel}"
        return html.escape(url, quote=True), ""

    file_uri = img_path.as_uri()
    return html.escape(file_uri, quote=True), ""


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _run_static_server(
    root: Path,
    *,
    port: int,
    html_url_to_print: str,
) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root.resolve()))
    server = _ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, name="classifier-test-http", daemon=True)
    thread.start()
    print("")
    print("Local server running (same origin for page + image). Open this URL in the browser:")
    print(f"  {html_url_to_print}")
    print("")
    print("(Do not use file:// for this test; extensions often treat each file URL as its own origin.)")
    try:
        input("Press Enter to stop the server…\n")
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "browser_classifier_test_output" / "classifier_extension_test.html",
        help=(
            "HTML filename or full path. With default --serve (session dir), only the basename "
            "is used inside the probe session folder. With --serve-in-place, the full path is used."
        ),
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Image file (source path). With default --serve it is copied into the session folder.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve image + HTML from http://127.0.0.1 (recommended; avoids file: origin issues).",
    )
    parser.add_argument(
        "--serve-in-place",
        action="store_true",
        help="With --serve: do not use a probe session dir; serve from common parent of image + --output (may fail across drives).",
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="With default --serve: do not delete the session folder after the server stops.",
    )
    parser.add_argument(
        "--serve-root",
        type=Path,
        default=None,
        help="With --serve-in-place only: static server root (must contain image and HTML). Default: common parent of their folders.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="TCP port for --serve (0 = pick a free port).",
    )
    args = parser.parse_args()

    if args.serve and args.image is None:
        raise SystemExit("--serve requires --image (embedded data-URI mode has no file to serve).")
    if args.serve_in_place and not args.serve:
        raise SystemExit("--serve-in-place requires --serve.")

    session_dir: Path | None = None
    port: int | None = None
    serve_root_resolved: Path | None = None
    html_url: str | None = None
    output_path: Path
    http_image_path: Path | None = None

    if args.serve and not args.serve_in_place:
        img_path = args.image.resolve()
        if not img_path.is_file():
            raise SystemExit(f"Image not found: {img_path}")
        session_dir = Path(
            tempfile.mkdtemp(prefix="probe_", dir=str(_probe_sessions_parent()))
        )
        dest_name = img_path.name
        dest_image = session_dir / dest_name
        if dest_image.exists():
            raise SystemExit(f"Unexpected name collision in session dir: {dest_image}")
        shutil.copy2(img_path, dest_image)
        output_path = session_dir / args.output.name
        serve_root_resolved = session_dir
        http_image_path = dest_image
        print(f"Probe session directory (not in git): {session_dir}")
    else:
        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if args.serve:
            img_path = args.image.resolve()
            if not img_path.is_file():
                raise SystemExit(f"Image not found: {img_path}")
            serve_root_resolved = _resolve_serve_root(img_path, output_path, args.serve_root)
            http_image_path = img_path

    if args.serve:
        assert serve_root_resolved is not None and http_image_path is not None
        port = _pick_listen_port(args.port)
        html_rel = _url_path_under_root(output_path.resolve(), serve_root_resolved.resolve())
        html_url = f"http://127.0.0.1:{port}/{html_rel}"

    img_src, img_dims = _build_img_src(
        args.image,
        serve=bool(args.serve),
        serve_root=serve_root_resolved,
        http_image_path=http_image_path,
        port=port,
    )

    content = HTML_TEMPLATE.format(img_src=img_src, img_dims=img_dims)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path}")
    if args.image and not args.serve:
        print(
            "Note: img uses a file: URL; many extensions block or isolate file origins. "
            "Re-run with --serve and open the http:// URL instead."
        )

    if args.serve:
        assert serve_root_resolved is not None and html_url is not None and port is not None
        try:
            _run_static_server(serve_root_resolved, port=port, html_url_to_print=html_url)
        finally:
            if session_dir is not None and not args.keep_session:
                shutil.rmtree(session_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
