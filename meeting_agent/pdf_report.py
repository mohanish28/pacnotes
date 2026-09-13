"""Renders the Gemini-enhanced Markdown notes (+ screenshot appendix) to a PDF."""
import os
from pathlib import Path

import markdown
from xhtml2pdf import pisa
from xhtml2pdf.config.resources import ResourceAccessPolicy

CSS = """
<style>
  body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #222; }
  h1 { font-size: 20pt; border-bottom: 2px solid #444; padding-bottom: 6px; }
  h2 { font-size: 14pt; color: #333; margin-top: 22px; }
  table { border-collapse: collapse; width: 100%; margin-top: 8px; }
  th, td { border: 1px solid #999; padding: 6px 8px; text-align: left; font-size: 10pt; }
  th { background-color: #eee; }
  /* xhtml2pdf silently mis-renders percentage widths on <img> -- the image
     embeds correctly (confirmed via pypdf: right byte count, right pixel
     data) but never actually appears on the page. A fixed px width is the
     one that reliably renders; 500px fits one page with margin to spare. */
  .screenshot { width: 500px; margin: 10px 0 18px 0; }
</style>
"""


def _link_callback(uri: str, _rel: str) -> str:
    # xhtml2pdf needs absolute filesystem paths to resolve local <img> sources.
    if os.path.isfile(uri):
        return uri
    return uri


def render_pdf(markdown_notes: str, screenshots: list[Path], output_path: Path) -> Path:
    body_html = markdown.markdown(markdown_notes, extensions=["tables"])

    screenshots_html = ""
    if screenshots:
        screenshots_html = "<h2>Screenshots</h2>"
        for shot in screenshots:
            screenshots_html += f'<img class="screenshot" src="{shot.resolve()}"/>'

    html = f"<html><head>{CSS}</head><body>{body_html}{screenshots_html}</body></html>"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # xhtml2pdf 's default resource policy confines local <img> reads to the
    # current working directory (an SSRF/local-file-disclosure guard) --
    # screenshots live in the session dir under output_dir, not necessarily
    # the process cwd, so that default silently drops every screenshot
    # instead of raising (confirmed live: PDF built "successfully" with the
    # image missing). Explicitly allow each screenshot's own directory.
    extra_roots = tuple({shot.resolve().parent for shot in screenshots})
    policy = ResourceAccessPolicy(extra_roots=extra_roots)
    with open(output_path, "wb") as f:
        result = pisa.CreatePDF(html, dest=f, link_callback=_link_callback, resource_policy=policy)

    if result.err:
        raise RuntimeError(f"PDF generation failed with {result.err} error(s).")
    return output_path
