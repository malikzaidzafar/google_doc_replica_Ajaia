"""Adversarial tests: try to break auth, access control, validation, the sanitizer and the error contract.

Each test plays an attacker or a careless client. Run:
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/docshare_test pytest -q tests/test_attack_security.py
"""
import json
from concurrent.futures import ThreadPoolExecutor
import time
from html.parser import HTMLParser
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

LEAK_MARKERS = ("Traceback", "sqlalchemy", "psycopg", "Exception", "pydantic", "input_value",
                '"loc"', "type_error", "errors.pydantic.dev", 'File "', "There was an error parsing the body")
NONEXISTENT = 10**6


# ---------- helpers ----------

def assert_human_error(resp, status):
    assert resp.status_code == status, (resp.status_code, resp.text)
    body = resp.json()
    assert set(body) == {"detail"} and isinstance(body["detail"], str) and body["detail"].strip(), body
    for marker in LEAK_MARKERS:
        assert marker not in resp.text, (marker, resp.text)


def new_doc(client, user, title="Doc"):
    resp = client.post("/api/documents", json={"title": title}, headers=user)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def put(client, user, doc_id, content="<p>x</p>", base=1, title="T"):
    return client.put(f"/api/documents/{doc_id}", json={"title": title, "content": content, "base_version": base},
                      headers=user)


def share(client, user, doc_id, email, role):
    return client.post(f"/api/documents/{doc_id}/shares", json={"email": email, "role": role}, headers=user)


def get(client, user, doc_id):
    return client.get(f"/api/documents/{doc_id}", headers=user)


def uid(user):
    return int(user["X-User-Id"])


# ---------- auth tampering ----------

BAD_IDS = ["", " ", "abc", "1; DROP TABLE users", "-1", "0", "1.5", "99999999999999999999",
           "9223372036854775808", "2147483648", "+1", "0_1", "1_0", "0x1", "1e3", "null", "true", "¹"]


@pytest.mark.parametrize("raw", BAD_IDS)
def test_forged_user_ids_are_rejected_cleanly(client, raw):
    # Header values travel as latin-1 bytes; httpx refuses non-ASCII str values, so send bytes.
    assert_human_error(client.get("/api/documents", headers={"X-User-Id": raw.encode("latin-1")}), 401)


def test_non_latin1_user_id_bytes_are_rejected(client):
    assert_human_error(client.get("/api/documents", headers={"X-User-Id": "١".encode()}), 401)


def test_every_protected_route_requires_sign_in(client, who):
    doc_id = new_doc(client, who["alice"])
    calls = [
        ("GET", "/api/documents", None), ("POST", "/api/documents", {}), ("GET", f"/api/documents/{doc_id}", None),
        ("PUT", f"/api/documents/{doc_id}", {"title": "t", "content": "<p></p>", "base_version": 1}),
        ("DELETE", f"/api/documents/{doc_id}", None),
        ("POST", f"/api/documents/{doc_id}/shares", {"email": "bob@example.com", "role": "editor"}),
        ("DELETE", f"/api/documents/{doc_id}/shares/2", None),
    ]
    for method, url, body in calls:
        assert_human_error(client.request(method, url, json=body), 401)
    assert_human_error(client.post("/api/documents/import", files={"file": ("a.txt", b"hi")}), 401)
    assert get(client, who["alice"], doc_id).status_code == 200  # nothing was deleted along the way


def test_duplicated_user_id_headers_do_not_crash(client):
    resp = client.get("/api/documents", headers=[("X-User-Id", "1"), ("X-User-Id", "2")])
    assert resp.status_code in (200, 401)
    for marker in LEAK_MARKERS:
        assert marker not in resp.text


# ---------- access control / IDOR ----------

def test_viewer_cannot_write_share_or_escalate(client, who):
    doc_id = new_doc(client, who["alice"])
    share(client, who["alice"], doc_id, "bob@example.com", "viewer")
    bob, base = who["bob"], f"/api/documents/{doc_id}"

    assert_human_error(put(client, bob, doc_id), 403)
    assert_human_error(client.delete(base, headers=bob), 403)
    assert_human_error(share(client, bob, doc_id, "carol@example.com", "editor"), 403)
    assert_human_error(share(client, bob, doc_id, "bob@example.com", "editor"), 403)  # self-promotion
    assert_human_error(client.delete(f"{base}/shares/{uid(bob)}", headers=bob), 403)
    doc = get(client, who["alice"], doc_id).json()
    assert doc["version"] == 1 and [s["role"] for s in doc["shares"]] == ["viewer"]


def test_editor_cannot_do_owner_things(client, who):
    doc_id = new_doc(client, who["alice"])
    share(client, who["alice"], doc_id, "bob@example.com", "editor")
    share(client, who["alice"], doc_id, "carol@example.com", "viewer")
    bob, base = who["bob"], f"/api/documents/{doc_id}"

    assert_human_error(client.delete(base, headers=bob), 403)
    assert_human_error(share(client, bob, doc_id, "carol@example.com", "editor"), 403)
    assert_human_error(share(client, bob, doc_id, "alice@example.com", "viewer"), 403)  # demote the owner
    assert_human_error(client.delete(f"{base}/shares/{uid(who['carol'])}", headers=bob), 403)
    roles = {s["name"]: s["role"] for s in get(client, who["alice"], doc_id).json()["shares"]}
    assert roles == {"Bob": "editor", "Carol": "viewer"}


def test_stranger_gets_identical_404_for_existing_and_missing_docs(client, who):
    """No existence oracle: a forbidden doc must look exactly like a doc that doesn't exist."""
    doc_id = new_doc(client, who["alice"])
    carol = who["carol"]

    def probe(target):
        body = {"title": "t", "content": "<p>pwn</p>", "base_version": 1}
        return [
            client.get(f"/api/documents/{target}", headers=carol),
            client.put(f"/api/documents/{target}", json=body, headers=carol),
            client.delete(f"/api/documents/{target}", headers=carol),
            share(client, carol, target, "carol@example.com", "editor"),
            client.delete(f"/api/documents/{target}/shares/{uid(who['bob'])}", headers=carol),
        ]

    for existing, missing in zip(probe(doc_id), probe(NONEXISTENT)):
        assert_human_error(existing, 404)
        assert (existing.status_code, existing.json()) == (missing.status_code, missing.json())
    assert get(client, who["alice"], doc_id).json()["content"] == "<p></p>"  # untouched


@pytest.mark.parametrize("raw", ["-1", "0", "abc", "1.0", "99999999999999999999", "9223372036854775808",
                                 "2147483648", "1e3", "%00", "1%20", "0x1"])
def test_weird_document_ids_are_a_clean_404(client, who, raw):
    assert_human_error(client.get(f"/api/documents/{raw}", headers=who["alice"]), 404)
    assert_human_error(put(client, who["alice"], raw), 404)
    assert_human_error(client.delete(f"/api/documents/{raw}/shares/{raw}", headers=who["alice"]), 404)


def test_unshare_cannot_reach_across_documents(client, who):
    alices = new_doc(client, who["alice"])
    carols = new_doc(client, who["carol"])
    share(client, who["alice"], alices, "bob@example.com", "editor")

    # Carol owns *a* doc, but that must not let her remove Bob from Alice's doc.
    assert client.delete(f"/api/documents/{carols}/shares/{uid(who['bob'])}", headers=who["carol"]).status_code == 200
    assert_human_error(client.delete(f"/api/documents/{alices}/shares/{uid(who['bob'])}", headers=who["carol"]), 404)
    assert get(client, who["bob"], alices).json()["role"] == "editor"


def test_owner_cannot_share_with_themselves_or_change_own_role(client, who):
    doc_id = new_doc(client, who["alice"])
    for email in ("alice@example.com", "  ALICE@Example.com "):
        assert_human_error(share(client, who["alice"], doc_id, email, "viewer"), 400)
    assert get(client, who["alice"], doc_id).json()["role"] == "owner"
    # Removing the owner's (non-existent) share row is a no-op, never a lock-out.
    client.delete(f"/api/documents/{doc_id}/shares/{uid(who['alice'])}", headers=who["alice"])
    assert get(client, who["alice"], doc_id).json()["role"] == "owner"


@pytest.mark.parametrize("role", ["owner", "admin", "EDITOR", "Viewer", "", None, 1, ["editor"]])
def test_role_injection_is_refused(client, who, role):
    doc_id = new_doc(client, who["alice"])
    resp = share(client, who["alice"], doc_id, "bob@example.com", role)
    assert_human_error(resp, 422)
    assert get(client, who["bob"], doc_id).status_code == 404


# ---------- version-check abuse ----------

@pytest.mark.parametrize("base", [-1, 0, 3, 999, 2**31, 2**63, 10**30])
def test_wrong_base_versions_never_overwrite(client, who, base):
    doc_id = new_doc(client, who["alice"])
    assert put(client, who["alice"], doc_id, "<p>first</p>", 1).status_code == 200
    resp = put(client, who["alice"], doc_id, "<p>evil</p>", base)
    assert resp.status_code in (409, 422), resp.text
    if resp.status_code == 409:
        assert resp.json()["detail"]["document"]["content"] == "<p>first</p>"
    else:
        assert_human_error(resp, 422)
    assert get(client, who["alice"], doc_id).json()["content"] == "<p>first</p>"


@pytest.mark.parametrize("base", ["abc", 1.5, None, [], {}, "1.5", ""])
def test_malformed_base_versions_are_human_422s(client, who, base):
    doc_id = new_doc(client, who["alice"])
    assert_human_error(put(client, who["alice"], doc_id, "<p>x</p>", base), 422)
    assert get(client, who["alice"], doc_id).json()["version"] == 1


def test_missing_base_version_is_refused(client, who):
    doc_id = new_doc(client, who["alice"])
    resp = client.put(f"/api/documents/{doc_id}", json={"title": "t", "content": "<p>x</p>"}, headers=who["alice"])
    assert_human_error(resp, 422)


def test_boolean_base_version_never_crashes_or_skips_the_check(client, who):
    doc_id = new_doc(client, who["alice"])
    put(client, who["alice"], doc_id, "<p>first</p>", 1)  # now version 2; True would mean 1 -> must not win
    resp = put(client, who["alice"], doc_id, "<p>evil</p>", True)
    assert resp.status_code in (409, 422)
    assert get(client, who["alice"], doc_id).json()["content"] == "<p>first</p>"


def test_mass_assignment_fields_are_ignored(client, who):
    doc_id = new_doc(client, who["alice"])
    share(client, who["alice"], doc_id, "bob@example.com", "editor")
    body = {"title": "t", "content": "<p>x</p>", "base_version": 1, "version": 999, "owner_id": uid(who["bob"]),
            "id": NONEXISTENT, "updated_by": uid(who["carol"]), "role": "owner"}
    assert client.put(f"/api/documents/{doc_id}", json=body, headers=who["bob"]).json() == {"version": 2}
    doc = get(client, who["alice"], doc_id).json()
    assert (doc["owner"]["name"], doc["version"], doc["updated_by"], doc["role"]) == ("Alice", 2, "Bob", "owner")
    assert get(client, who["bob"], doc_id).json()["role"] == "editor"


def test_replaying_the_same_base_version_is_refused(client, who):
    doc_id = new_doc(client, who["alice"])
    first = put(client, who["alice"], doc_id, "<p>one</p>", 1)
    replay = put(client, who["alice"], doc_id, "<p>one</p>", 1)
    assert first.status_code == 200 and replay.status_code == 409


# ---------- input validation ----------

@pytest.mark.parametrize("title, stored", [
    ("   \t\n  ", "Untitled document"),
    ("​​﻿", "Untitled document"),           # invisible-only title
    ("a\nb\r\nc\td", "a b c d"),                          # newlines/tabs flattened
    ("a\x00b\x07c", "abc"),                               # NUL/control chars would crash Postgres
    ("invoice‮gpj.exe", "invoicegpj.exe"),           # RTL-override spoofing
    ("é" * 200, "é" * 200),
    ("😀" * 200, "😀" * 200),
    ("<script>alert(1)</script>", "<script>alert(1)</script>"),  # titles are plain text, rendered escaped
])
def test_titles_are_normalized_safely(client, who, title, stored):
    created = client.post("/api/documents", json={"title": title}, headers=who["alice"])
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    assert get(client, who["alice"], doc_id).json()["title"] == stored
    assert put(client, who["alice"], doc_id, "<p>x</p>", 1, title=title).status_code == 200
    assert get(client, who["alice"], doc_id).json()["title"] == stored


def test_title_length_limit(client, who):
    doc_id = new_doc(client, who["alice"])
    assert put(client, who["alice"], doc_id, base=1, title="a" * 200).status_code == 200
    resp = put(client, who["alice"], doc_id, base=2, title="a" * 201)
    assert_human_error(resp, 422)
    assert "200" in resp.json()["detail"]
    assert_human_error(client.post("/api/documents", json={"title": "b" * 201}, headers=who["alice"]), 422)


def test_content_size_limit_is_exact(client, who):
    doc_id = new_doc(client, who["alice"])
    wrap = len("<p></p>")
    assert put(client, who["alice"], doc_id, "<p>" + "a" * (1_000_000 - wrap) + "</p>", 1).status_code == 200
    resp = put(client, who["alice"], doc_id, "<p>" + "a" * (1_000_001 - wrap) + "</p>", 2)
    assert_human_error(resp, 413)
    assert get(client, who["alice"], doc_id).json()["version"] == 2


def test_nul_bytes_in_content_do_not_crash_the_save(client, who):
    doc_id = new_doc(client, who["alice"])
    resp = put(client, who["alice"], doc_id, "<p>a\x00b</p>", 1)
    assert resp.status_code == 200, resp.text
    assert "\x00" not in get(client, who["alice"], doc_id).json()["content"]


@pytest.mark.parametrize("raw, ctype", [
    (b'{"title": ', "application/json"),                 # truncated JSON
    (b"[1, 2, 3]", "application/json"),                  # array instead of object
    (b'"just a string"', "application/json"),
    (b"title=x&content=y&base_version=1", "application/x-www-form-urlencoded"),
    (b'{"title": "t", "content": "<p>x</p>", "base_version": 1}', "text/plain"),
    (b"\xff\xfe\x00garbage", "application/json"),        # not UTF-8
    (b"[" * 100_000 + b"]" * 100_000, "application/json"),  # deeply nested JSON
])
def test_garbage_bodies_get_human_errors(client, who, raw, ctype):
    doc_id = new_doc(client, who["alice"])
    resp = client.put(f"/api/documents/{doc_id}", content=raw, headers={**who["alice"], "Content-Type": ctype})
    assert 400 <= resp.status_code < 500, resp.text
    assert_human_error(resp, resp.status_code)
    assert get(client, who["alice"], doc_id).json()["version"] == 1


@pytest.mark.parametrize("email, status", [
    ("' OR 1=1 --", 422),                               # spaces: rejected before any query
    ("bob@example.com' --", 422),
    ("'OR'1'='1", 400),                                  # reaches the (parameterized) query: just no match
    ("bob@example.com'--", 400),
    ("x@y.z');DELETE/**/FROM/**/users;--", 400),
    ("bob@exаmple.com", 400),                           # Cyrillic 'а' homoglyph
    ("bob@example.com\x00", 422),
    ("bob\x00@example.com", 422),
    ("bob @example.com", 422),
    ("", 422),
    ("a" * 300 + "@example.com", 422),
    (None, 422),
    (["bob@example.com"], 422),
])
def test_hostile_share_emails(client, who, email, status):
    doc_id = new_doc(client, who["alice"])
    assert_human_error(share(client, who["alice"], doc_id, email, "editor"), status)
    assert get(client, who["alice"], doc_id).json()["shares"] == []


def test_share_email_is_normalized(client, who):
    doc_id = new_doc(client, who["alice"])
    resp = share(client, who["alice"], doc_id, "  BOB@Example.COM\t", "viewer")
    assert resp.status_code == 200 and [s["name"] for s in resp.json()["shares"]] == ["Bob"]
    again = share(client, who["alice"], doc_id, "bob@example.com", "editor")  # re-share updates, never duplicates
    assert [(s["name"], s["role"]) for s in again.json()["shares"]] == [("Bob", "editor")]


# ---------- stored XSS: the sanitizer ----------

XSS_PAYLOADS = [
    "<svg onload=alert(1)>",
    "<svg><script>alert(1)</script></svg>",
    "<img src=x onerror=alert(1)>",
    "<iframe src=javascript:alert(1)></iframe>",
    '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
    '<math><mi xlink:href="javascript:alert(1)">x</mi></math>',
    '<a href="JaVaScRiPt:alert(1)">x</a>',
    '<a href="&#106;avascript:alert(1)">x</a>',
    '<a href="&#x6A;&#x61;vascript:alert(1)">x</a>',
    '<a href="java\tscript:alert(1)">x</a>',
    '<a href="java&#9;script:alert(1)">x</a>',
    '<a href=" javascript:alert(1)">x</a>',
    '<a href="javascript&colon;alert(1)">x</a>',
    '<a href="vbscript:msgbox(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
    '<a href="x" onmouseover="alert(1)" style="position:fixed;inset:0">x</a>',
    '<p style="background:url(javascript:alert(1))">x</p>',
    '<form action="javascript:alert(1)"><button>go</button></form>',
    '<base href="javascript:alert(1)//">',
    '<meta http-equiv="refresh" content="0;url=javascript:alert(1)">',
    "<scr<script>ipt>alert(1)</scr</script>ipt>",
    "<!--<script>alert(1)</script>-->",
    '"><script>alert(1)</script>',
    "<p title=\"</p><img src=x onerror=alert(1)>\">x</p>",
    "<noscript><p title=\"</noscript><img src=x onerror=alert(1)>\"></noscript>",
    "<svg><p><style><img src=x onerror=alert(1)></style></p></svg>",
    "<math><mtext><table><mglyph><style><img src=x onerror=alert(1)></style></mglyph></table></mtext></math>",
    "<object data=javascript:alert(1)></object><embed src=javascript:alert(1)>",
    "<details open ontoggle=alert(1)>",
    "<video><source onerror=alert(1)></video>",
    '<input autofocus onfocus=alert(1)>',
    "<template><script>alert(1)</script></template>",
    '<ol start="1" onclick="alert(1)" type="javascript:alert(1)"><li>x</li></ol>',
    '<a href="//evil.example/x" target="_blank" rel="opener">x</a>',
    '<link rel=stylesheet href="https://evil.example/x.css"><style>@import "https://evil.example";</style>',
]

ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "a", "code", "pre", "blockquote", "hr",
                "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li"}
ALLOWED_ATTRS = {"a": {"href", "rel"}, "ol": {"start"}}


class _TagAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.problems.append(f"tag <{tag}>")
        for name, value in attrs:
            if name not in ALLOWED_ATTRS.get(tag, set()):
                self.problems.append(f"attr {tag}.{name}")
            if name == "href":
                cleaned = "".join(ch for ch in (value or "") if ch > " ").lower()
                if urlparse(cleaned).scheme not in {"", "http", "https", "mailto"}:
                    self.problems.append(f"href {value!r}")
            if name == "rel" and "opener" in (value or "").split():
                self.problems.append("rel=opener")

    handle_startendtag = handle_starttag


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_stored_content_has_no_executable_vector(client, who, payload):
    doc_id = new_doc(client, who["alice"])
    resp = put(client, who["alice"], doc_id, f"<p>before</p>{payload}<p>after</p>", 1)
    assert resp.status_code == 200, resp.text
    content = get(client, who["alice"], doc_id).json()["content"]
    audit = _TagAudit()
    audit.feed(content)
    audit.close()
    assert audit.problems == [], (payload, content, audit.problems)
    assert "before" in content and "after" in content  # sanitizing strips the attack, not the document


def test_409_payload_is_sanitized_too(client, who):
    doc_id = new_doc(client, who["alice"])
    put(client, who["alice"], doc_id, "<p>ok</p><img src=x onerror=alert(1)>", 1)
    stale = put(client, who["alice"], doc_id, "<p>later</p>", 1)
    assert stale.status_code == 409 and "onerror" not in stale.json()["detail"]["document"]["content"]


# ---------- denial of service through the sanitizer ----------

@pytest.mark.parametrize("unit", ["<ul><li>", "<div>", "<blockquote>", "<ol><li><p>", "<div/>", "<b><div></b>",
                                  "<div></zz>", "<DIV>", "<d\x00iv>"])
def test_deeply_nested_markup_cannot_pin_the_cpu(client, who, unit):
    """80 KB of nested lists took ~17 s in the sanitizer (quadratic); a 1 MB save could block a worker for minutes."""
    doc_id = new_doc(client, who["alice"])
    payload = unit * (900_000 // len(unit))
    started = time.monotonic()
    resp = put(client, who["alice"], doc_id, payload, 1)
    elapsed = time.monotonic() - started
    assert elapsed < 5, f"{unit!r}: {elapsed:.1f}s"
    assert resp.status_code in (200, 400), resp.text
    if resp.status_code == 400:
        assert_human_error(resp, 400)


def test_large_but_flat_documents_still_save_quickly(client, who):
    """The nesting guard must not reject real documents: 1 MB of paragraphs and moderately nested lists."""
    doc_id = new_doc(client, who["alice"])
    nested = "<ul>" + "<li>item<ul>" * 10 + "<li>deep</li>" + "</ul></li>" * 10 + "</ul>"
    block = "<h2>Section</h2><p>Some <strong>bold</strong> and <em>italic</em> text.</p>" + nested
    payload = block * (990_000 // len(block))
    started = time.monotonic()
    resp = put(client, who["alice"], doc_id, payload, 1)
    assert resp.status_code == 200, resp.text
    assert time.monotonic() - started < 10
    assert "<li>deep</li>" in get(client, who["alice"], doc_id).json()["content"]


# ---------- error contract ----------

def test_framework_errors_are_humanized(client, who):
    assert_human_error(client.get("/api/nope", headers=who["alice"]), 404)
    assert_human_error(client.get("/nope"), 404)
    assert_human_error(client.patch("/api/documents/1", json={}, headers=who["alice"]), 405)
    assert_human_error(client.post("/api/users", json={}), 405)
    assert_human_error(client.put("/api/documents", json={}, headers=who["alice"]), 405)


def test_unexpected_crash_is_generic_and_leaks_nothing(client, who, monkeypatch):
    from main import app
    from services import documents

    def boom(*_args, **_kwargs):
        raise RuntimeError('psycopg.errors.UndefinedTable: relation "documents" sqlalchemy Traceback secret=hunter2')

    monkeypatch.setattr(documents, "list_for_user", boom)
    with TestClient(app, raise_server_exceptions=False) as crashy:
        resp = crashy.get("/api/documents", headers=who["alice"])
    assert_human_error(resp, 500)
    assert "hunter2" not in resp.text and "relation" not in resp.text


def test_409_body_has_the_documented_shape(client, who):
    doc_id = new_doc(client, who["alice"])
    put(client, who["alice"], doc_id, "<p>a</p>", 1)
    body = put(client, who["alice"], doc_id, "<p>b</p>", 1).json()
    assert set(body) == {"detail"} and set(body["detail"]) == {"message", "document"}
    assert body["detail"]["message"] == "Alice saved a newer version while you were editing."
    for marker in LEAK_MARKERS:
        assert marker not in json.dumps(body)


# ---------- data integrity ----------

def test_deleted_document_is_gone_for_everyone(client, who):
    doc_id = new_doc(client, who["alice"])
    share(client, who["alice"], doc_id, "bob@example.com", "editor")
    assert client.delete(f"/api/documents/{doc_id}", headers=who["alice"]).status_code == 204

    for user in (who["alice"], who["bob"]):
        assert_human_error(get(client, user, doc_id), 404)
        assert_human_error(put(client, user, doc_id, base=1), 404)
        assert_human_error(share(client, user, doc_id, "carol@example.com", "viewer"), 404)
        assert_human_error(client.delete(f"/api/documents/{doc_id}", headers=user), 404)
        listing = client.get("/api/documents", headers=user).json()
        assert doc_id not in [d["id"] for d in listing["owned"] + listing["shared"]]

    from db import engine, shares
    with engine.connect() as conn:
        left = conn.execute(select(func.count()).select_from(shares).where(shares.c.document_id == doc_id)).scalar()
    assert left == 0


def test_lists_follow_access_changes(client, who):
    doc_id = new_doc(client, who["alice"], title="Moving target")

    def bobs_view():
        listing = client.get("/api/documents", headers=who["bob"]).json()
        assert doc_id not in [d["id"] for d in listing["owned"]]
        return {d["id"]: d["role"] for d in listing["shared"]}.get(doc_id)

    assert bobs_view() is None
    share(client, who["alice"], doc_id, "bob@example.com", "viewer")
    assert bobs_view() == "viewer"
    share(client, who["alice"], doc_id, "bob@example.com", "editor")
    assert bobs_view() == "editor"
    client.delete(f"/api/documents/{doc_id}/shares/{uid(who['bob'])}", headers=who["alice"])
    assert bobs_view() is None
    assert_human_error(get(client, who["bob"], doc_id), 404)
    alices = client.get("/api/documents", headers=who["alice"]).json()
    assert doc_id in [d["id"] for d in alices["owned"]] and doc_id not in [d["id"] for d in alices["shared"]]


def test_viewer_sees_no_more_than_needed_after_losing_access_mid_session(client, who):
    doc_id = new_doc(client, who["alice"])
    share(client, who["alice"], doc_id, "bob@example.com", "editor")
    assert put(client, who["bob"], doc_id, "<p>bob 1</p>", 1).status_code == 200
    share(client, who["alice"], doc_id, "bob@example.com", "viewer")  # downgraded mid-edit
    assert_human_error(put(client, who["bob"], doc_id, "<p>bob 2</p>", 2), 403)
    client.delete(f"/api/documents/{doc_id}/shares/{uid(who['bob'])}", headers=who["alice"])  # then removed
    assert_human_error(put(client, who["bob"], doc_id, "<p>bob 3</p>", 2), 404)
    assert get(client, who["alice"], doc_id).json()["content"] == "<p>bob 1</p>"


# ---------- races through real concurrent requests ----------

@pytest.fixture(scope="module")
def raw_client(client):
    """Returns 500s as responses instead of raising, so racing threads can report what users would see."""
    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_double_click_reshare_never_500(raw_client, who):
    """Select-then-insert raced into a duplicate-key 500; re-sharing must be an upsert."""
    for _ in range(3):
        doc_id = new_doc(raw_client, who["alice"])
        with ThreadPoolExecutor(12) as pool:
            codes = list(pool.map(
                lambda i: share(raw_client, who["alice"], doc_id, "bob@example.com",
                                "editor" if i % 2 else "viewer").status_code, range(24)))
        assert set(codes) == {200}, codes
        assert [s["name"] for s in get(raw_client, who["alice"], doc_id).json()["shares"]] == ["Bob"]


def test_share_racing_delete_never_500(raw_client, who):
    """A share landing after the doc row vanished hit a foreign-key 500; it must be a 404 (or win before delete)."""
    for _ in range(5):
        doc_id = new_doc(raw_client, who["alice"])

        def act(i):
            if i == 4:
                return raw_client.delete(f"/api/documents/{doc_id}", headers=who["alice"])
            return share(raw_client, who["alice"], doc_id, ["bob", "carol"][i % 2] + "@example.com", "editor")

        with ThreadPoolExecutor(9) as pool:
            responses = list(pool.map(act, range(9)))
        assert {r.status_code for r in responses} <= {200, 204, 404}, [(r.status_code, r.text) for r in responses]
        for r in responses:
            if r.status_code == 404:
                assert_human_error(r, 404)
        assert get(raw_client, who["alice"], doc_id).status_code == 404


def test_5000_deep_blockquote_is_refused_fast(client, who):
    doc_id = new_doc(client, who["alice"])
    started = time.monotonic()
    resp = put(client, who["alice"], doc_id, "<blockquote>" * 5000 + "x" + "</blockquote>" * 5000, 1)
    assert time.monotonic() - started < 1
    assert_human_error(resp, 400)
    assert "nesting" in resp.json()["detail"]


@pytest.mark.parametrize("ctype, body", [
    ("multipart/form-data", b"--x\r\n"),                       # no boundary parameter
    ("multipart/form-data; boundary=abc", b"garbage without parts"),
])
def test_broken_multipart_uploads_get_human_errors(client, who, ctype, body):
    resp = client.post("/api/documents/import", content=body, headers={**who["alice"], "Content-Type": ctype})
    assert 400 <= resp.status_code < 500
    assert_human_error(resp, resp.status_code)
    assert "multipart" not in resp.text.lower() and "boundary" not in resp.text.lower()
