"""Adversarial tests: real concurrency against a live server, and hostile file uploads.

Runs its own uvicorn (port 8011) on TEST_DATABASE_URL so requests really race through Postgres.
Run from backend/:
  TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/docshare_test2 .venv/bin/pytest -q tests/test_attack_races_imports.py
"""
import io
import os
import socket
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parent.parent
PORT = 8011
BASE = f"http://127.0.0.1:{PORT}"
MB = 1024 * 1024
SLOW = 5.0  # no single hostile import may tie up a worker longer than this (seconds)


# ---------- live server ----------

@pytest.fixture(scope="module")
def server(tmp_path_factory):
    env = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]}  # conftest already enforced localhost
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            pytest.fail(f"port {PORT} is busy (a stale test server?); refusing to test against it")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True,
                   capture_output=True)
    log = tmp_path_factory.mktemp("server") / "uvicorn.log"
    with open(log, "w") as out:
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(PORT),
                                 "--log-level", "warning"], cwd=BACKEND, env=env, stdout=out, stderr=out)
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{BASE}/api/users", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            pytest.fail("uvicorn never came up:\n" + log.read_text())
        yield log
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:  # a worker stuck in a hostile request; don't leave it behind
            proc.kill()
            proc.wait(10)


@pytest.fixture(scope="module")
def api(server):
    with httpx.Client(base_url=BASE, timeout=60) as client:
        yield client


@pytest.fixture(scope="module")
def ids(api):
    return {u["name"].lower(): u["id"] for u in api.get("/api/users").json()}


def H(uid):
    return {"X-User-Id": str(uid)}


def new_doc(api, uid, title="Attack doc"):
    r = api.post("/api/documents", json={"title": title}, headers=H(uid))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def share(api, owner, doc_id, email, role):
    return api.post(f"/api/documents/{doc_id}/shares", json={"email": email, "role": role}, headers=H(owner))


def put(client, uid, doc_id, content, base_version, title="Attack doc"):
    return client.put(f"/api/documents/{doc_id}", headers=H(uid),
                      json={"title": title, "content": content, "base_version": base_version})


def parallel(fn, args_list, workers=20):
    """Release all calls at once (barrier) so they genuinely overlap on the server."""
    barrier = threading.Barrier(len(args_list))

    def run(args):
        with httpx.Client(base_url=BASE, timeout=60) as client:
            barrier.wait()
            return fn(client, *args)

    with ThreadPoolExecutor(max_workers=max(workers, len(args_list))) as pool:
        return list(pool.map(run, args_list))


def assert_human_error(r, *statuses):
    assert r.status_code in statuses, (r.status_code, r.text)
    detail = r.json()["detail"]
    assert isinstance(detail, str) and detail.strip()
    for leak in ("Traceback", "Exception", "Error", "psycopg", "sqlalchemy", "line "):
        assert leak not in detail, detail


# ---------- concurrency attacks ----------

def test_twenty_writers_same_base_version_exactly_one_wins(api, ids):
    alice = ids["alice"]
    doc_id = new_doc(api, alice)
    results = parallel(lambda c, i: (i, put(c, alice, doc_id, f"<p>writer {i}</p>", 1)), [(i,) for i in range(20)])
    winners = [i for i, r in results if r.status_code == 200]
    losers = [r for _, r in results if r.status_code == 409]
    assert len(winners) == 1 and len(losers) == 19, [r.status_code for _, r in results]
    for r in losers:  # every loser is told who won and gets the winning content, never a 500
        assert r.json()["detail"]["document"]["content"] == f"<p>writer {winners[0]}</p>"
    doc = api.get(f"/api/documents/{doc_id}", headers=H(alice)).json()
    assert (doc["version"], doc["content"]) == (2, f"<p>writer {winners[0]}</p>")


def test_interleaved_writers_never_lose_an_update(api, ids):
    alice, bob = ids["alice"], ids["bob"]
    doc_id = new_doc(api, alice)
    assert share(api, alice, doc_id, "bob@example.com", "editor").status_code == 200
    successes, lock = [], threading.Lock()

    def writer(client, uid, name):
        version = 1
        for round_no in range(10):
            content = f"<p>{name} round {round_no}</p>"
            for _attempt in range(50):
                r = put(client, uid, doc_id, content, version)
                if r.status_code == 200:
                    version = r.json()["version"]
                    with lock:
                        successes.append((version, content))
                    break
                assert r.status_code == 409, r.text
                version = r.json()["detail"]["document"]["version"]  # rebase on what the server has
            else:
                pytest.fail("writer starved")

    parallel(writer, [(alice, "alice"), (bob, "bob")])
    versions = sorted(v for v, _ in successes)
    assert versions == list(range(2, 2 + len(successes))), "two saves claimed the same version"
    doc = api.get(f"/api/documents/{doc_id}", headers=H(alice)).json()
    assert doc["version"] == 1 + len(successes) == 21
    assert doc["content"] == max(successes)[1], "final content is not the last acknowledged save"


def test_unshare_while_saving_never_500_and_locks_out_afterwards(api, ids):
    alice, bob = ids["alice"], ids["bob"]
    doc_id = new_doc(api, alice)
    share(api, alice, doc_id, "bob@example.com", "editor")
    unshared_at = []

    def act(client, i):
        if i == 10:
            r = client.delete(f"/api/documents/{doc_id}/shares/{bob}", headers=H(alice))
            unshared_at.append(time.monotonic())
            return r
        version = client.get(f"/api/documents/{doc_id}", headers=H(bob))
        base = version.json()["version"] if version.status_code == 200 else 1
        return put(client, bob, doc_id, f"<p>bob {i}</p>", base)

    results = parallel(act, [(i,) for i in range(21)])
    assert all(r.status_code in (200, 403, 404, 409) for r in results), [r.status_code for r in results]
    for _ in range(5):  # strictly after the unshare: always 404, for reads and writes
        assert api.get(f"/api/documents/{doc_id}", headers=H(bob)).status_code == 404
        assert put(api, bob, doc_id, "<p>sneaky</p>", 999).status_code == 404


def test_delete_while_saves_and_polls_in_flight(api, ids):
    alice, bob = ids["alice"], ids["bob"]
    doc_id = new_doc(api, alice)
    share(api, alice, doc_id, "bob@example.com", "editor")

    def act(client, i):
        if i == 0:
            return client.delete(f"/api/documents/{doc_id}", headers=H(alice))
        if i % 2:
            return client.get(f"/api/documents/{doc_id}", headers=H(bob))
        return put(client, bob, doc_id, f"<p>{i}</p>", 1)

    results = parallel(act, [(i,) for i in range(21)])
    assert results[0].status_code == 204
    assert all(r.status_code in (200, 204, 404, 409) for r in results), [r.status_code for r in results]
    assert api.get(f"/api/documents/{doc_id}", headers=H(alice)).status_code == 404  # not resurrected
    shared = api.get("/api/documents", headers=H(bob)).json()["shared"]
    assert all(d["id"] != doc_id for d in shared)  # no orphan share rows


def test_downgrade_to_viewer_during_saves(api, ids):
    alice, bob = ids["alice"], ids["bob"]
    doc_id = new_doc(api, alice)
    share(api, alice, doc_id, "bob@example.com", "editor")

    def act(client, i):
        if i == 5:
            return share(client, alice, doc_id, "bob@example.com", "viewer")
        return put(client, bob, doc_id, f"<p>{i}</p>", 1)

    results = parallel(act, [(i,) for i in range(20)])
    assert all(r.status_code in (200, 403, 409) for r in results), [r.status_code for r in results]
    after = put(api, bob, doc_id, "<p>after</p>", 99)
    assert_human_error(after, 403)


def test_concurrent_reshare_same_person_never_500(api, ids):
    """Two tabs (or a double-click) sharing with the same person at the same moment."""
    alice = ids["alice"]
    doc_id = new_doc(api, alice)
    results = parallel(lambda c, role: share(c, alice, doc_id, "carol@example.com", role),
                       [("editor" if i % 2 else "viewer",) for i in range(10)])
    assert all(r.status_code == 200 for r in results), [(r.status_code, r.text[:80]) for r in results]


def test_share_racing_delete_never_500(api, ids):
    alice = ids["alice"]
    for _ in range(5):
        doc_id = new_doc(api, alice)

        def act(client, i):
            if i == 0:
                return client.delete(f"/api/documents/{doc_id}", headers=H(alice))
            return share(client, alice, doc_id, "bob@example.com", "editor")

        results = parallel(act, [(i,) for i in range(8)])
        assert all(r.status_code in (200, 204, 404) for r in results), [(r.status_code, r.text[:80]) for r in results]


def test_fifty_concurrent_creates_and_imports(api, ids):
    users = list(ids.values())

    def act(client, i):
        uid = users[i % len(users)]
        if i % 2:
            return client.post("/api/documents/import", headers=H(uid),
                                files={"file": (f"n{i}.md", f"# Note {i}\n\n**x**".encode())})
        return client.post("/api/documents", json={"title": f"Doc {i}"}, headers=H(uid))

    results = parallel(act, [(i,) for i in range(50)], workers=50)
    assert all(r.status_code == 201 for r in results), [(r.status_code, r.text[:80]) for r in results]
    assert len({r.json()["id"] for r in results}) == 50


def test_presence_sees_others_never_self(api, ids):
    alice = ids["alice"]
    doc_id = new_doc(api, alice)
    share(api, alice, doc_id, "bob@example.com", "editor")
    share(api, alice, doc_id, "carol@example.com", "viewer")
    names = {ids["alice"]: "Alice", ids["bob"]: "Bob", ids["carol"]: "Carol"}
    for uid in names:  # everyone polls once
        api.get(f"/api/documents/{doc_id}", headers=H(uid))
    results = parallel(lambda c, uid: (uid, c.get(f"/api/documents/{doc_id}", headers=H(uid)).json()),
                       [(uid,) for uid in names])
    for uid, doc in results:
        assert sorted(doc["active_users"]) == sorted(n for u, n in names.items() if u != uid)


# ---------- hostile uploads ----------

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
)
ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
    ' Target="word/document.xml"/></Relationships>'
)
W = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
     'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')


def make_docx(body_xml="", doctype="", doc_rels="", extra=None, document_xml=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/document.xml", document_xml if document_xml is not None else (
            f'<?xml version="1.0" encoding="UTF-8"?>{doctype}<w:document {W}><w:body>{body_xml}</w:body></w:document>'))
        if doc_rels:
            z.writestr("word/_rels/document.xml.rels", (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{doc_rels}'
                "</Relationships>"))
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return buffer.getvalue()


def para(text):
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def upload(api, uid, name, data, field="file"):
    started = time.monotonic()
    r = api.post("/api/documents/import", headers=H(uid), files={field: (name, data, "application/octet-stream")})
    elapsed = time.monotonic() - started
    assert elapsed < SLOW, f"import of {name!r} took {elapsed:.1f}s"
    return r


def imported(api, uid, r):
    assert r.status_code == 201, r.text
    return api.get(f"/api/documents/{r.json()['id']}", headers=H(uid)).json()


def test_zip_bombs_are_rejected_quickly(api, ids):
    alice = ids["alice"]
    one_huge = make_docx(extra={"word/media/pad.bin": b"\0" * (50 * MB)})
    many = make_docx(extra={f"word/media/p{i}.bin": b"\0" * MB for i in range(30)})
    for name, data in (("one-huge.docx", one_huge), ("many-parts.docx", many)):
        assert len(data) < 2 * MB
        assert_human_error(upload(api, alice, name, data), 400)


def _lie_about_size(data: bytes, entry: str, claimed: int) -> bytes:
    """Patch both the local header and central directory to claim `entry` is tiny."""
    buf = bytearray(data)
    info = zipfile.ZipFile(io.BytesIO(data)).getinfo(entry)
    buf[info.header_offset + 22:info.header_offset + 26] = claimed.to_bytes(4, "little")
    name = entry.encode()
    pos = buf.find(b"PK\x01\x02")
    while pos != -1:
        name_len = int.from_bytes(buf[pos + 28:pos + 30], "little")
        if bytes(buf[pos + 46:pos + 46 + name_len]) == name:
            buf[pos + 24:pos + 28] = claimed.to_bytes(4, "little")
        pos = buf.find(b"PK\x01\x02", pos + 4)
    return bytes(buf)


def test_zip_header_lying_about_size_cannot_inflate(api, ids):
    padding = "<!--" + "x" * (40 * MB) + "-->"
    real = make_docx(document_xml=f'<?xml version="1.0"?><w:document {W}><w:body>{para("hi")}{padding}</w:body></w:document>')
    liar = _lie_about_size(real, "word/document.xml", 2000)
    assert sum(i.file_size for i in zipfile.ZipFile(io.BytesIO(liar)).infolist()) < MB  # passes the naive guard
    assert_human_error(upload(api, ids["alice"], "liar.docx", liar), 400)


def test_nested_zip_inside_docx_is_not_unpacked(api, ids):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bomb.bin", b"\0" * (100 * MB))
    data = make_docx(para("outer text"), extra={"word/embeddings/inner.zip": inner.getvalue()})
    doc = imported(api, ids["alice"], upload(api, ids["alice"], "nested.docx", data))
    assert "outer text" in doc["content"]


def test_xxe_does_not_leak_local_files(api, ids):
    doctype = '<!DOCTYPE w:document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
    r = upload(api, ids["alice"], "xxe.docx", make_docx(para("start &xxe; end"), doctype=doctype))
    if r.status_code == 201:
        content = imported(api, ids["alice"], r)["content"]
        assert "root:" not in content and "/bin/" not in content
    else:
        assert_human_error(r, 400)


def test_external_dtd_is_never_fetched(api, ids):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(1.5)
    port = listener.getsockname()[1]
    doctype = f'<!DOCTYPE w:document SYSTEM "http://127.0.0.1:{port}/evil.dtd">'
    r = upload(api, ids["alice"], "dtd.docx", make_docx(para("hello"), doctype=doctype))
    assert r.status_code in (201, 400), r.text
    with pytest.raises(socket.timeout):
        listener.accept()  # the server must not have called out to our "attacker" host
    listener.close()


def test_billion_laughs_is_rejected_quickly(api, ids):
    levels = '<!ENTITY lol0 "lol">' + "".join(
        f'<!ENTITY lol{i} "{"&lol%d;" % (i - 1) * 10}">' for i in range(1, 10))
    r = upload(api, ids["alice"], "laughs.docx", make_docx(para("&lol9;"), doctype=f"<!DOCTYPE w:document [{levels}]>"))
    if r.status_code == 201:
        assert len(imported(api, ids["alice"], r)["content"]) < 1_000_000
    else:
        assert_human_error(r, 400, 413)


def test_docx_with_image_table_and_javascript_link_is_defanged(api, ids):
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
    drawing = (
        '<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        '<wp:docPr id="1" name="Picture 1" descr="alt"/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:blipFill><a:blip r:embed="rId5"/>'
        "</pic:blipFill></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>")
    table = '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell text</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    link = '<w:p><w:hyperlink r:id="rId6"><w:r><w:t>click me</w:t></w:r></w:hyperlink></w:p>'
    rels = ('<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="media/image1.png"/>'
            '<Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="javascript:alert(document.cookie)" TargetMode="External"/>')
    data = make_docx(drawing + table + link, doc_rels=rels, extra={"word/media/image1.png": png})
    content = imported(api, ids["alice"], upload(api, ids["alice"], "rich.docx", data))["content"]
    assert "cell text" in content and "click me" in content
    for banned in ("<img", "data:", "<table", "javascript", "alert"):
        assert banned not in content, banned


def test_slow_docx_of_tiny_paragraphs_is_refused_quickly(api, ids):
    """A ~5 KB .docx with 50k empty-ish paragraphs used to take ~25 s in mammoth, holding a DB connection."""
    data = make_docx(para("a") * 50_000)
    assert len(data) < 50_000
    assert_human_error(upload(api, ids["alice"], "slow.docx", data), 400)


@pytest.mark.parametrize("name, data", [
    ("renamed-pdf.docx", b"%PDF-1.7\n%\xe2\xe3\xcf\xd3 fake"),
    ("renamed-png.docx", b"\x89PNG\r\n\x1a\n" + b"\0" * 100),
    ("renamed-elf.docx", b"\x7fELF\x02\x01\x01" + b"\0" * 100),
    ("renamed-elf.txt", b"\x7fELF\x02\x01\x01\xff\xfe" + b"\0" * 100),
    ("renamed-png.md", b"\x89PNG\r\n\x1a\n\xff\xd8"),
    ("text-not-zip.docx", b"PK but not really a zip"),
    ("a.txt.docx", b"plain text pretending"),
    ("notes.md.exe", b"# hi"),
    (".md", b"# hidden file"),
    ("noextension", b"hello"),
])
def test_disguised_files_are_rejected_cleanly(api, ids, name, data):
    assert_human_error(upload(api, ids["alice"], name, data), 400)


def test_extension_case_and_odd_names(api, ids):
    alice = ids["alice"]
    assert imported(api, alice, upload(api, alice, "SHOUT.DOCX", make_docx(para("loud"))))["title"] == "SHOUT"
    assert imported(api, alice, upload(api, alice, "../../etc/passwd.md", b"# x"))["title"] == "passwd"
    long_doc = imported(api, alice, upload(api, alice, "n" * 1000 + ".txt", b"x"))
    assert len(long_doc["title"]) == 200
    emoji = imported(api, alice, upload(api, alice, "plan 🚀 Zoë.md", b"# x"))
    assert emoji["title"] == "plan 🚀 Zoë"
    spoof = imported(api, alice, upload(api, alice, "invoice\u202etxt.exe.md", b"x"))
    assert "\u202e" not in spoof["title"]


def test_null_bytes_in_name_and_text_do_not_crash(api, ids):
    alice = ids["alice"]
    doc = imported(api, alice, upload(api, alice, "nul\x00name.txt", b"hello\x00world\nline two"))
    assert "\x00" not in doc["title"] and "\x00" not in doc["content"]
    assert "helloworld" in doc["content"]
    md = imported(api, alice, upload(api, alice, "nul.md", b"# head\x00ing\n\ntext\x00"))
    assert "\x00" not in md["content"]


def test_missing_or_wrong_file_fields(api, ids):
    alice = H(ids["alice"])
    assert_human_error(api.post("/api/documents/import", headers=alice), 422)
    assert_human_error(api.post("/api/documents/import", headers=alice, files={"upload": ("a.md", b"# x")}), 422)
    empty_name = api.post("/api/documents/import", headers=alice, files={"file": ("", b"# x")})
    assert_human_error(empty_name, 400, 422)
    two = api.post("/api/documents/import", headers=alice,
                   files=[("file", ("one.md", b"# one")), ("file", ("two.md", b"# two"))])
    assert two.status_code in (201, 400, 422), two.text  # one doc at most, never a 500
    if two.status_code == 201:
        assert api.get(f"/api/documents/{two.json()['id']}", headers=alice).json()["title"] in ("one", "two")


@pytest.mark.parametrize("name, data", [
    ("utf16.txt", "hello".encode("utf-16")),
    ("latin1.md", "café crème".encode("latin-1")),
    ("zero.txt", b""),
    ("spaces.md", b" \n\t\r\n  "),
])
def test_unreadable_or_empty_text(api, ids, name, data):
    assert_human_error(upload(api, ids["alice"], name, data), 400)


def test_size_boundaries(api, ids):
    alice = ids["alice"]
    exactly = b"\n" * (2 * MB - 2) + b"hi"
    assert len(exactly) == 2 * MB
    assert imported(api, alice, upload(api, alice, "exact.md", exactly))["content"] == "<p>hi</p>"
    over = upload(api, alice, "over.md", exactly + b"!")
    assert_human_error(over, 413)
    assert "2 MB" in over.json()["detail"]


def test_imported_doc_is_never_too_big_to_save(api, ids):
    """Conversion inflates text; a doc that imports but can never be saved again is a trap."""
    alice = ids["alice"]
    for name, data in (("lines.txt", b"\n".join(b"line %d" % i for i in range(150_000))),
                       ("one-line.txt", b"<" * (1_900_000))):
        assert len(data) <= 2 * MB
        r = upload(api, alice, name, data)
        if r.status_code == 201:
            doc = imported(api, alice, r)
            saved = put(api, alice, doc["id"], doc["content"], doc["version"], title=doc["title"])
            assert saved.status_code == 200, f"imported {name} but can't save it: {saved.text[:120]}"
        else:
            assert_human_error(r, 413)


def test_crlf_and_many_lines(api, ids):
    alice = ids["alice"]
    doc = imported(api, alice, upload(api, alice, "crlf.txt", b"first\r\nsecond\r\n"))
    assert doc["content"] == "<p>first</p><p>second</p>"
    many = imported(api, alice, upload(api, alice, "many.txt", b"\n".join(b"l" for _ in range(100_000))))
    assert many["content"].count("<p>") == 100_000


def test_markdown_injection_is_stripped(api, ids):
    alice = ids["alice"]
    md = (b"# Title\n\n<script>alert(1)</script>\n\n[click](javascript:alert(1))\n\n"
          b"<!-- secret comment -->\n\n<img src=x onerror=alert(1)>\n\n<a href=\"jAvAsCrIpT:alert(1)\">x</a>\n\n"
          b"<svg onload=alert(1)></svg><iframe src=\"https://evil.example\"></iframe>")
    content = imported(api, alice, upload(api, alice, "evil.md", md))["content"]
    assert "<h1>Title</h1>" in content
    for banned in ("<script", "javascript", "onerror", "onload", "<img", "<svg", "<iframe", "secret comment"):
        assert banned not in content.lower(), banned


@pytest.mark.parametrize("name, source", [
    ("many-paragraphs.md", "a\n\n" * 100_000),
    ("many-headings.md", "# h\n" * 50_000),
    ("quotes.md", "> " * 1000 + "deep"),
    ("quotes-100k.md", "> " * 100_000 + "deep"),
    ("lists.md", "\n".join("    " * i + "- x" for i in range(1000))),
    ("raw-divs.md", "<div>" * 20_000 + "x" + "</div>" * 20_000),
    ("raw-quotes.md", "<blockquote>" * 100_000 + "x"),
])
def test_expensive_markdown_is_refused_quickly(api, ids, name, source):
    data = source.encode()
    assert len(data) <= 2 * MB
    assert_human_error(upload(api, ids["alice"], name, data), 400)


def test_blank_line_flood_imports_quickly(api, ids):
    doc = imported(api, ids["alice"], upload(api, ids["alice"], "blank.md", b"\n \n" * 600_000 + b"hi"))
    assert doc["content"] == "<p>hi</p>"


def test_reasonable_nesting_still_imports(api, ids):
    alice = ids["alice"]
    nested = "\n".join("  " * i + "- level %d" % i for i in range(8))
    doc = imported(api, alice, upload(api, alice, "nested.md", ("> > quoted\n\n" + nested).encode()))
    assert "level 7" in doc["content"] and "<blockquote>" in doc["content"]


@pytest.mark.parametrize("headers, body", [
    ({"Content-Type": "text/plain"}, b"just text"),
    ({"Content-Type": "multipart/form-data"}, b"--x\r\nContent-Disposition: form-data; name=\"file\"\r\n\r\nhi\r\n--x--"),
    ({"Content-Type": "multipart/form-data; boundary=" + "b" * 5000},
     b"--" + b"b" * 5000 + b"\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.md\"\r\n\r\n# hi\r\n--"
     + b"b" * 5000 + b"--\r\n"),
    ({"Content-Type": "multipart/form-data; boundary=zz"}, b"garbage without any boundary"),
])
def test_multipart_abuse_never_500(api, ids, headers, body):
    r = api.post("/api/documents/import", headers={**H(ids["alice"]), **headers}, content=body)
    assert r.status_code in (201, 400, 413, 422), r.text
    if r.status_code != 201:
        assert_human_error(r, r.status_code)


def test_server_logged_no_unhandled_errors(server):
    """Runs last in this module: any 500 above would have left a traceback in the server log."""
    log = server.read_text()
    assert "Unhandled error" not in log and "Traceback" not in log, log[-3000:]
