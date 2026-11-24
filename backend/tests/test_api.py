"""API tests: access rules, conflict detection, sanitizing, sharing, import, humanized errors.

Run from backend/:  TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/postgres pytest -q
"""
import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from db import engine, shares
from main import app
from services import documents as documents_service


def new_doc(client, headers, title="Doc"):
    return client.post("/api/documents", json={"title": title}, headers=headers).json()["id"]


def save(client, headers, doc_id, content, base_version, title="T"):
    return client.put(f"/api/documents/{doc_id}", json={"title": title, "content": content, "base_version": base_version}, headers=headers)


def share(client, headers, doc_id, email, role):
    return client.post(f"/api/documents/{doc_id}/shares", json={"email": email, "role": role}, headers=headers)


def test_seed_data_is_present(client, who):
    assert set(who) == {"alice", "bob", "carol"}
    shared = client.get("/api/documents", headers=who["carol"]).json()["shared"]
    assert [(d["title"], d["owner_name"], d["role"]) for d in shared] == [("Welcome to DocShare", "Alice", "viewer")]


def test_sharing_controls_access(client, who):
    doc_id = new_doc(client, who["alice"], "Roadmap")
    url = f"/api/documents/{doc_id}"

    # Not shared: Bob can't see it, can't share it to himself, and it isn't in his list.
    assert client.get(url, headers=who["bob"]).status_code == 404
    assert share(client, who["bob"], doc_id, "bob@example.com", "editor").status_code == 404
    assert all(d["id"] != doc_id for d in client.get("/api/documents", headers=who["bob"]).json()["shared"])

    # Viewer: can read and sees it under "shared", but saving is refused.
    assert share(client, who["alice"], doc_id, "bob@example.com", "viewer").status_code == 200
    listed = next(d for d in client.get("/api/documents", headers=who["bob"]).json()["shared"] if d["id"] == doc_id)
    assert (listed["owner_name"], listed["role"]) == ("Alice", "viewer")
    assert client.get(url, headers=who["bob"]).json()["role"] == "viewer"
    refused = save(client, who["bob"], doc_id, "<p>Bob</p>", 1)
    assert refused.status_code == 403 and "Ask the owner" in refused.json()["detail"]

    # Editor: saving works; owner-only actions don't.
    share(client, who["alice"], doc_id, "bob@example.com", "editor")
    assert save(client, who["bob"], doc_id, "<p>Bob</p>", 1).status_code == 200
    assert client.delete(url, headers=who["bob"]).status_code == 403
    assert share(client, who["bob"], doc_id, "carol@example.com", "viewer").status_code == 403

    # Access removed: back to 404.
    client.delete(f"{url}/shares/{who['bob']['X-User-Id']}", headers=who["alice"])
    assert client.get(url, headers=who["bob"]).status_code == 404


def test_stale_save_is_rejected_instead_of_overwriting(client, who):
    doc_id = new_doc(client, who["alice"])
    assert save(client, who["alice"], doc_id, "<p>first</p>", 1).json() == {"version": 2}

    stale = save(client, who["alice"], doc_id, "<p>stale</p>", 1)  # a second tab still on version 1
    assert stale.status_code == 409
    assert stale.json()["detail"]["message"] == "Alice saved a newer version while you were editing."
    assert stale.json()["detail"]["document"]["content"] == "<p>first</p>"
    assert client.get(f"/api/documents/{doc_id}", headers=who["alice"]).json()["content"] == "<p>first</p>"


def test_saved_html_is_sanitized(client, who):
    doc_id = new_doc(client, who["alice"])
    dirty = '<p onclick="x()">hi <strong>there</strong><script>alert(1)</script><a href="javascript:x()">l</a><img src=x></p>'
    save(client, who["alice"], doc_id, dirty, 1)
    content = client.get(f"/api/documents/{doc_id}", headers=who["alice"]).json()["content"]
    assert "<strong>there</strong>" in content
    for bad in ("script", "onclick", "javascript", "<img"):
        assert bad not in content


def test_delete_cascades_shares(client, who):
    doc_id = new_doc(client, who["alice"])
    share(client, who["alice"], doc_id, "bob@example.com", "editor")
    assert client.delete(f"/api/documents/{doc_id}", headers=who["alice"]).status_code == 204
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).where(shares.c.document_id == doc_id)).scalar() == 0
    assert client.get(f"/api/documents/{doc_id}", headers=who["bob"]).status_code == 404


def test_share_edge_cases(client, who):
    doc_id = new_doc(client, who["alice"])
    unknown = share(client, who["alice"], doc_id, "nobody@example.com", "viewer")
    assert unknown.status_code == 400 and "no account for nobody@example.com" in unknown.json()["detail"]
    assert share(client, who["alice"], doc_id, "alice@example.com", "viewer").status_code == 400

    share(client, who["alice"], doc_id, "  BOB@Example.COM ", "viewer")  # trimmed + lowercased
    again = share(client, who["alice"], doc_id, "bob@example.com", "editor").json()["shares"]  # re-share = role change
    assert [(s["name"], s["role"]) for s in again] == [("Bob", "editor")]


def test_titles_default_and_content_size_is_capped(client, who):
    blank = client.post("/api/documents", json={"title": "   "}, headers=who["alice"]).json()["id"]
    no_body = client.post("/api/documents", headers=who["alice"]).json()["id"]
    for doc_id in (blank, no_body):
        assert client.get(f"/api/documents/{doc_id}", headers=who["alice"]).json()["title"] == "Untitled document"
    save(client, who["alice"], blank, "<p>x</p>", 1, title="")
    assert client.get(f"/api/documents/{blank}", headers=who["alice"]).json()["title"] == "Untitled document"

    too_big = save(client, who["alice"], blank, "<p>" + "a" * 1_000_001 + "</p>", 2)
    assert too_big.status_code == 413 and "too large" in too_big.json()["detail"]


def upload(client, headers, name, data):
    return client.post("/api/documents/import", files={"file": (name, data)}, headers=headers)


def test_markdown_import_keeps_structure(client, who):
    md = b"# Plan\n\nSome **bold** and *italic* text.\n\n- one\n- two\n\n1. first\n2. second\n\n<script>x()</script>"
    r = upload(client, who["alice"], "q3-plan.md", md)
    assert r.status_code == 201
    doc = client.get(f"/api/documents/{r.json()['id']}", headers=who["alice"]).json()
    assert doc["title"] == "q3-plan"
    for fragment in ("<h1>Plan</h1>", "<strong>bold</strong>", "<em>italic</em>", "<ul>", "<ol>", "<li>two</li>"):
        assert fragment in doc["content"]
    assert "script" not in doc["content"]


def make_docx(body_xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"))
        z.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"))
        z.writestr("word/document.xml", (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body_xml}</w:body></w:document>"))
    return buffer.getvalue()


def test_docx_import_keeps_bold_and_underline(client, who):
    body = (
        '<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>bold</w:t></w:r><w:r><w:t xml:space="preserve"> and </w:t></w:r>'
        '<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>under</w:t></w:r></w:p>'
    )
    r = upload(client, who["alice"], "Report.docx", make_docx(body))
    assert r.status_code == 201
    doc = client.get(f"/api/documents/{r.json()['id']}", headers=who["alice"]).json()
    assert doc["title"] == "Report"
    assert "<strong>bold</strong>" in doc["content"] and "<u>under</u>" in doc["content"]


def test_import_rejects_bad_files(client, who):
    def status(name, data):
        return upload(client, who["alice"], name, data).status_code

    assert status("slides.pdf", b"%PDF-1.4") == 400
    assert status("empty.txt", b"  \n") == 400
    assert status("latin1.txt", "café".encode("latin-1")) == 400
    assert status("big.txt", b"a" * (2 * 1024 * 1024 + 1)) == 413
    assert status("renamed.docx", b"%PDF-1.4 not a zip") == 400

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"0" * (21 * 1024 * 1024))  # compresses to ~20 KB
    r = upload(client, who["alice"], "bomb.docx", bomb.getvalue())
    assert r.status_code == 400 and "20 MB" in r.json()["detail"]


def test_errors_are_humanized(client, who):
    assert client.get("/api/documents").json()["detail"] == "Please sign in to continue."
    assert client.get("/api/documents", headers={"X-User-Id": "abc"}).status_code == 401
    assert client.get("/api/documents/abc", headers=who["alice"]).json()["detail"] == "We couldn't find that document."
    assert client.get("/api/nope").json()["detail"] == "We couldn't find what you were looking for."

    doc_id = new_doc(client, who["alice"])
    long_title = save(client, who["alice"], doc_id, "<p></p>", 1, title="x" * 201)
    assert (long_title.status_code, long_title.json()["detail"]) == (422, "Title is too long (max 200 characters).")
    bad_role = share(client, who["alice"], doc_id, "bob@example.com", "admin")
    assert bad_role.json()["detail"] == "Choose either 'Can edit' or 'View only'."
    no_file = client.post("/api/documents/import", headers=who["alice"])
    assert no_file.json()["detail"] == "Choose a file to upload."


def test_unexpected_errors_return_generic_message(who, monkeypatch, client):
    def boom(*_args):
        raise RuntimeError("psycopg.OperationalError: secret internals")

    monkeypatch.setattr(documents_service, "list_for_user", boom)
    with TestClient(app, raise_server_exceptions=False) as quiet_client:
        r = quiet_client.get("/api/documents", headers=who["alice"])
    assert r.status_code == 500
    assert r.json() == {"detail": "Something went wrong on our side. Your changes are still on this page; please try again."}
    assert "secret" not in r.text
