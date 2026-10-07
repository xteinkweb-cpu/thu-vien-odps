#!/usr/bin/env python3
"""Đọc danh sách file sách trong các Release của repo này và tạo catalog OPDS (site/opds.xml)."""
import json, os, shutil, urllib.request, uuid
from datetime import datetime, timezone
from xml.sax.saxutils import escape

SITE_DIR = "site"
MIME = {
    ".epub": "application/epub+zip",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".fb2": "application/x-fictionbook+xml",
    ".xtc": "application/octet-stream",
    ".xtch": "application/octet-stream",
}


def base_url():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        if name.lower() == f"{owner.lower()}.github.io":
            return f"https://{owner.lower()}.github.io"
        return f"https://{owner.lower()}.github.io/{name}"
    return "http://localhost:8000"


def api_get(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + os.environ.get("GITHUB_TOKEN", ""),
            "User-Agent": "opds-builder",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def paged(path):
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        items = api_get(f"{path}{sep}per_page=100&page={page}")
        if not items:
            return
        yield from items
        if len(items) < 100:
            return
        page += 1


def list_assets():
    repo = os.environ["GITHUB_REPOSITORY"]
    out = []
    for rel in paged(f"/repos/{repo}/releases"):
        if rel.get("draft"):
            continue
        for a in paged(f"/repos/{repo}/releases/{rel['id']}/assets"):
            out.append(
                {"name": a["name"], "url": a["browser_download_url"], "size": a["size"]}
            )
    return out


def title_author(filename):
    stem = os.path.splitext(filename)[0]
    author = "Không rõ"
    if "__" in stem:
        stem, author = stem.split("__", 1)
        author = author.replace(".", " ").replace("_", " ").replace("-", " ").strip() or "Không rõ"
    title = stem.replace(".", " ").replace("_", " ").replace("-", " ").strip() or filename
    return title, author


def build(assets):
    if os.path.exists(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(SITE_DIR)
    open(os.path.join(SITE_DIR, ".nojekyll"), "w").close()

    base = base_url()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    books = []
    for a in assets:
        ext = os.path.splitext(a["name"])[1].lower()
        if ext in MIME:
            t, au = title_author(a["name"])
            books.append((t, au, a["url"], ext))
    books.sort(key=lambda b: b[0].lower())

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/terms/">',
        f"  <id>urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, base)}</id>",
        "  <title>Thư viện của tôi</title>",
        f"  <updated>{now}</updated>",
        "  <author><name>Thư viện cá nhân</name></author>",
        f'  <link rel="self" href="{base}/opds.xml" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>',
        f'  <link rel="start" href="{base}/opds.xml" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>',
    ]
    for title, author, url, ext in books:
        xml += [
            "  <entry>",
            f"    <title>{escape(title)}</title>",
            f"    <id>urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, url)}</id>",
            f"    <updated>{now}</updated>",
            f"    <author><name>{escape(author)}</name></author>",
            f'    <link rel="http://opds-spec.org/acquisition" href="{escape(url, {chr(34): "&quot;"})}" type="{MIME[ext]}"/>',
            "  </entry>",
        ]
    xml.append("</feed>")
    with open(os.path.join(SITE_DIR, "opds.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(xml) + "\n")
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            '<!doctype html><meta charset="utf-8"><title>Thư viện</title>'
            f"<h1>Thư viện OPDS</h1><p>Địa chỉ nhập vào máy đọc: <code>{base}/opds.xml</code></p>"
            f"<p>Số sách: {len(books)}</p>"
        )
    print(f"Đã tạo catalog với {len(books)} sách.")
    print(f"Địa chỉ OPDS: {base}/opds.xml")


if __name__ == "__main__":
    build(list_assets())
