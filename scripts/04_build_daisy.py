"""Bước 4: book.json + timing.json + metadata.json → out/<slug>/ (thư mục sách DAISY 3).

Sinh: dtbook.xml · <nhóm>.smil (1 file / mp3) · navigation.ncx · package.opf · resources.res,
và copy mp3. Chỉ đưa vào sách những nhóm ĐÃ có audio trong timing.json — nên dựng thử vài
truyện vẫn ra một cuốn sách mở được; đủ 101 nhóm thì là bản nộp.

Kiểm chứng cuối script (fail nếu sai): số <sent>/<h1>/<h2>/<dateline> có smilref trong dtbook
= số <par> trong tất cả smil; mọi smilref trỏ tới id tồn tại; dtb:totalTime = tổng mp3.

    .venv/bin/python scripts/04_build_daisy.py            # metadata còn CHUA_DIEN → chỉ cảnh báo
    .venv/bin/python scripts/04_build_daisy.py --strict   # bản nộp: CHUA_DIEN → dừng
"""
import json
import re
import shutil
import sys
from xml.sax.saxutils import escape, quoteattr

# Console Windows mặc định không phải UTF-8 → in tiếng Việt vào file/pipe sẽ lỗi
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from book_units import (BUILD, NOTE_LABEL, ROOT, groups_in_order, iter_units, load_book,
                        load_metadata)

MP3_DIR = BUILD / "mp3"
GENERATOR = "daisy-pipeline-vieneu (scripts/04_build_daisy.py)"
NOTE_MARK = re.compile(r"\[(\d+)\]")


def clock(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:06.3f}"


class Daisy:
    def __init__(self, strict):
        self.meta = load_metadata()
        self.book = load_book()
        self.timing = json.loads((BUILD / "timing.json").read_text(encoding="utf-8"))
        self.out = ROOT / "out" / self.meta["slug"]
        self.uid = self.meta["source"] if not self.meta["source"].startswith("CHUA_DIEN") else "TEMP-UID"
        placeholders = [k for k, v in self.meta.items() if isinstance(v, str) and v.startswith("CHUA_DIEN")] + \
                       [f"mshv[{i}]" for i, v in enumerate(self.meta["mshv"]) if v.startswith("CHUA_DIEN")]
        if placeholders:
            msg = f"metadata.json chưa điền: {placeholders}"
            if strict:
                sys.exit("DỪNG (--strict): " + msg)
            print("CẢNH BÁO:", msg)
        # clip[id] = (group, begin, end); chỉ nhóm có audio
        self.clip = {cid: (g, b, e) for g, t in self.timing.items() for cid, b, e in t["clips"]}
        self.groups = [g for g in groups_in_order(self.book) if g in self.timing]
        self.units_by_group = {}
        for u in iter_units(self.book):
            self.units_by_group.setdefault(u.group, []).append(u)
        self.notes_by_n = {n["n"]: n for n in self.book["notes"]}
        self.play_order = 0
        self.n_sync = 0        # số phần tử có smilref trong dtbook

    # ---------- tiện ích ----------
    def has(self, uid):
        return uid in self.clip

    def smilref(self, uid):
        g = self.clip[uid][0]
        return f"{g}.smil#par_{uid}"

    def audio_tag(self, uid):
        g, b, e = self.clip[uid]
        return f'<audio src="{g}.mp3" clipBegin="{clock(b)}" clipEnd="{clock(e)}"/>'

    def inline(self, raw):
        """Text có [n] → text + <noteref>. Escape XML trước, chèn thẻ sau."""
        parts, pos = [], 0
        for m in NOTE_MARK.finditer(raw):
            parts.append(escape(raw[pos:m.start()]))
            parts.append(f'<noteref idref="#note{m.group(1)}" class="noteref">[{m.group(1)}]</noteref>')
            pos = m.end()
        parts.append(escape(raw[pos:]))
        return "".join(parts)

    def sync_attrs(self, uid):
        if not self.has(uid):
            return f'id="{uid}"'
        self.n_sync += 1
        return f'id="{uid}" smilref="{self.smilref(uid)}"'

    # ---------- DTBook ----------
    def dtbook(self):
        m = self.meta
        L = ['<?xml version="1.0" encoding="utf-8"?>',
             '<?xml-stylesheet type="text/css" href="dtbook.css"?>',
             '<!DOCTYPE dtbook PUBLIC "-//NISO//DTD dtbook 2005-3//EN" "http://www.daisy.org/z3986/2005/dtbook-2005-3.dtd">',
             '<dtbook xmlns="http://www.daisy.org/z3986/2005/dtbook/" version="2005-3" xml:lang="vi">',
             '<head>']
        for k, v in [("dtb:uid", self.uid), ("dc:Title", m["title"]), ("dc:Creator", m["creator"]),
                     ("dc:Publisher", m["publisher"]), ("dc:Date", m["date"]), ("dc:Language", "vi"),
                     ("dc:Identifier", self.uid), ("dtb:generator", GENERATOR)]:
            L.append(f'<meta name="{k}" content={quoteattr(v)}/>')
        L += ['</head>', '<book showin="blp">', '<frontmatter>',
              f'<doctitle {self.sync_attrs("doctitle")}>{escape(m["title"])}</doctitle>',
              f'<docauthor {self.sync_attrs("docauthor")}>{escape(m["creator"])}</docauthor>',
              '</frontmatter>', '<bodymatter id="bodymatter">']
        for lv in self.book["levels"]:
            if lv["id"] not in self.timing:
                continue
            L.append(f'<level1 id="{lv["id"]}-level">')
            L.append(f'<h1 {self.sync_attrs(lv["id"])}>{self.inline(lv["title"])}</h1>')
            L += self.notes(lv["id"], lv["noterefs"])
            L += self.paragraphs(lv["id"], lv["paragraphs"])
            for ch in lv["chapters"]:
                if ch["id"] not in self.timing:
                    continue
                L.append(f'<level2 id="{ch["id"]}-level">')
                L.append(f'<h2 {self.sync_attrs(ch["id"])}>{self.inline(ch["title"])}</h2>')
                refs = list(ch["noterefs"])
                if ch["dateline"]:
                    d = ch["dateline"]
                    L.append(f'<dateline {self.sync_attrs(d["id"])}>{self.inline(d["raw"])}</dateline>')
                    refs += d["noterefs"]
                L += self.notes(ch["id"], refs)
                L += self.paragraphs(ch["id"], ch["paragraphs"])
                L.append('</level2>')
            L.append('</level1>')
        L += ['</bodymatter>', '</book>', '</dtbook>']
        return "\n".join(L)

    def sents(self, sentences):
        return " ".join(f'<sent {self.sync_attrs(s["id"])}>{self.inline(s["raw"])}</sent>' for s in sentences)

    def paragraphs(self, group, paras):
        out = []
        for p in paras:
            out.append(f'<p id="{p["id"]}">{self.sents(p["sentences"])}</p>')
            out += self.notes(group, [n for s in p["sentences"] for n in s["noterefs"]])
        return out

    def notes(self, group, refs):
        """<note> đặt ngay sau khối chứa [n]; skippable qua seq class="note" trong SMIL."""
        out = []
        for n in refs:
            note = self.notes_by_n[n]
            label = f'<sent {self.sync_attrs(note["id"] + "-label")}>{escape(NOTE_LABEL)}</sent>'
            out.append(f'<note id="{note["id"]}" class="footnote" smilref="{group}.smil#seq_{note["id"]}">'
                       f'<p id="{note["id"]}-p">{label} {self.sents(note["sentences"])}</p></note>')
        return out

    # ---------- SMIL ----------
    def smil(self, group, elapsed):
        t = self.timing[group]
        L = ['<?xml version="1.0" encoding="utf-8"?>',
             '<!DOCTYPE smil PUBLIC "-//NISO//DTD dtbsmil 2005-2//EN" "http://www.daisy.org/z3986/2005/dtbsmil-2005-2.dtd">',
             '<smil xmlns="http://www.w3.org/2001/SMIL20/">', '<head>',
             f'<meta name="dtb:uid" content={quoteattr(self.uid)}/>',
             f'<meta name="dtb:totalElapsedTime" content="{clock(elapsed)}"/>',
             f'<meta name="dtb:generator" content={quoteattr(GENERATOR)}/>',
             '<customAttributes>',
             '<customTest id="note" defaultState="true" override="visible"/>',
             '<customTest id="noteref" defaultState="false" override="visible"/>',
             '</customAttributes>', '</head>', '<body>',
             f'<seq id="root-seq" dur="{clock(t["duration"])}">']
        cur_p, cur_note, n_par = None, None, 0
        units = self.units_by_group[group]
        for u in units:
            p_of = self.paragraph_of.get(u.id)
            note_of = self.note_of.get(u.id)
            # Thứ tự đóng: đoạn (trong) trước, chú thích (ngoài) sau; mở thì ngược lại
            if p_of != cur_p and cur_p:
                L.append('</seq>')
                cur_p = None
            if note_of != cur_note:
                if cur_note:
                    L.append('</seq>')
                cur_note = note_of
                if cur_note:
                    L.append(f'<seq id="seq_{cur_note}" class="note" customTest="note">')
            if p_of != cur_p:
                cur_p = p_of
                if cur_p:
                    L.append(f'<seq id="seq_{cur_p}" class="p">')
            L.append(f'<par id="par_{u.id}" class="{u.kind}">'
                     f'<text src="dtbook.xml#{u.id}"/>{self.audio_tag(u.id)}</par>')
            n_par += 1
        if cur_p:
            L.append('</seq>')
        if cur_note:
            L.append('</seq>')
        L += ['</seq>', '</body>', '</smil>']
        return "\n".join(L), n_par

    def index_paragraphs(self):
        """id câu → id đoạn (để bọc <seq class="p">), id câu chú thích → id note."""
        self.paragraph_of, self.note_of = {}, {}
        for lv in self.book["levels"]:
            for h in [lv, *lv["chapters"]]:
                for p in h["paragraphs"]:
                    for s in p["sentences"]:
                        self.paragraph_of[s["id"]] = p["id"]
        for note in self.book["notes"]:
            for sid in [note["id"] + "-label", *(s["id"] for s in note["sentences"])]:
                self.paragraph_of[sid] = f'{note["id"]}-p'
                self.note_of[sid] = note["id"]

    # ---------- NCX ----------
    def nav_point(self, uid, label, cls, children=()):
        """children: list (uid, label, cls) — đánh playOrder cho cha TRƯỚC rồi mới tới con."""
        self.play_order += 1
        L = [f'<navPoint id="nav-{uid}" class="{cls}" playOrder="{self.play_order}">',
             f'<navLabel><text>{escape(label)}</text>{self.audio_tag(uid)}</navLabel>',
             f'<content src="{self.smilref(uid)}"/>']
        for c in children:
            L += self.nav_point(*c)
        L.append('</navPoint>')
        return L

    def ncx(self):
        m = self.meta
        L = ['<?xml version="1.0" encoding="utf-8"?>',
             '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">',
             '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="vi">', '<head>',
             f'<meta name="dtb:uid" content={quoteattr(self.uid)}/>',
             '<meta name="dtb:depth" content="2"/>',
             f'<meta name="dtb:generator" content={quoteattr(GENERATOR)}/>',
             '<meta name="dtb:totalPageCount" content="0"/>', '<meta name="dtb:maxPageNumber" content="0"/>',
             '<smilCustomTest id="note" defaultState="true" override="visible" bookStruct="NOTE"/>',
             '<smilCustomTest id="noteref" defaultState="false" override="visible" bookStruct="NOTE_REFERENCE"/>',
             '</head>',
             f'<docTitle><text>{escape(m["title"])}</text>{self.audio_tag("doctitle") if self.has("doctitle") else ""}</docTitle>',
             f'<docAuthor><text>{escape(m["creator"])}</text>{self.audio_tag("docauthor") if self.has("docauthor") else ""}</docAuthor>',
             '<navMap>']
        for lv in self.book["levels"]:
            if lv["id"] not in self.timing:
                continue
            children = [(ch["id"], ch["speech"], "level2")
                        for ch in lv["chapters"] if ch["id"] in self.timing]
            L += self.nav_point(lv["id"], lv["speech"], "level1", children)
        L += ['</navMap>', '</ncx>']
        return "\n".join(L)

    # ---------- OPF ----------
    def opf(self, total):
        m = self.meta
        dc = [("Title", m["title"]), ("Creator", m["creator"]), ("Contributor", m["contributor"]),
              ("Subject", m["subject"]), ("Description", m["description"]), ("Publisher", m["publisher"]),
              ("Date", m["date"]), ("Source", m["source"]), ("Language", m["language"]),
              ("Format", "ANSI/NISO Z39.86-2005")]
        L = ['<?xml version="1.0" encoding="utf-8"?>',
             '<!DOCTYPE package PUBLIC "+//ISBN 0-9673008-1-9//DTD OEB 1.2 Package//EN" "http://openebook.org/dtds/oeb-1.2/oebpkg12.dtd">',
             '<package xmlns="http://openebook.org/namespaces/oeb-package/1.0/" unique-identifier="uid">',
             '<metadata>', '<dc-metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:oebpackage="http://openebook.org/namespaces/oeb-package/1.0/">']
        L += [f'<dc:{k}>{escape(v)}</dc:{k}>' for k, v in dc]
        L.append(f'<dc:Identifier id="uid">{escape(self.uid)}</dc:Identifier>')
        L += ['</dc-metadata>', '<x-metadata>']
        for k, v in [("dtb:multimediaType", "audioFullText"), ("dtb:multimediaContent", "audio,text"),
                     ("dtb:totalTime", clock(total)), ("dtb:audioFormat", "MP3"),
                     ("dtb:narrator", m["narrator"]), ("dtb:producer", ", ".join(m["mshv"])),
                     ("dtb:sourceDate", m["date"]), ("dtb:sourcePublisher", m["publisher"]),
                     ("sourceURL", m["sourceURL"]), ("note", m["note"]), ("collector", m["collector"])]:
            L.append(f'<meta name="{k}" content={quoteattr(v)}/>')
        L += ['</x-metadata>', '</metadata>', '<manifest>',
              '<item href="package.opf" id="opf" media-type="text/xml"/>',
              '<item href="dtbook.xml" id="dtbook" media-type="application/x-dtbook+xml"/>',
              '<item href="navigation.ncx" id="ncx" media-type="application/x-dtbncx+xml"/>',
              '<item href="resources.res" id="resource" media-type="application/x-dtbresource+xml"/>',
              '<item href="dtbook.css" id="css" media-type="text/css"/>']
        for g in self.groups:
            L.append(f'<item href="{g}.smil" id="smil-{g}" media-type="application/smil"/>')
            L.append(f'<item href="{g}.mp3" id="mp3-{g}" media-type="audio/mpeg"/>')
        L += ['</manifest>', '<spine>']
        L += [f'<itemref idref="smil-{g}"/>' for g in self.groups]
        L += ['</spine>', '</package>']
        return "\n".join(L)

    # ---------- trang QA ----------
    def qa_page(self):
        """out/qa.html: nghe từng câu kèm id + mốc thời gian, ghi nhận lỗi, xuất CSV.
        Template là code (scripts/qa_template.html); file sinh ra nhúng dữ liệu vì mở file:// không fetch được."""
        levels, titles = [], {}
        for lv in self.book["levels"]:
            titles[lv["id"]] = lv["speech"]
            groups = [lv["id"]] + [ch["id"] for ch in lv["chapters"]]
            for ch in lv["chapters"]:
                titles[ch["id"]] = ch["speech"]
            gs = [self.qa_group(g, titles[g] if g != lv["id"] else "▸ " + lv["speech"])
                  for g in groups if g in self.timing]
            if gs:
                levels.append({"title": lv["speech"], "groups": gs})
        data = {"slug": self.meta["slug"], "levels": levels}
        html = (ROOT / "scripts" / "qa_template.html").read_text(encoding="utf-8")
        html = html.replace("__TITLE__", escape(self.meta["title"])).replace(
            "__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
        (self.out.parent / "qa.html").write_text(html, encoding="utf-8")

    def qa_group(self, g, title):
        t = self.timing[g]
        text_of = {u.id: u for u in self.units_by_group[g]}
        clips = [{"id": cid, "b": b, "e": e, "kind": text_of[cid].kind, "text": text_of[cid].text,
                  "p": self.paragraph_of.get(cid, cid)} for cid, b, e in t["clips"]]
        return {"id": g, "title": title, "mp3": f'{self.out.name}/{t["mp3"]}', "duration": t["duration"],
                "n": sum(c["kind"] in ("sent", "note_sent") for c in clips), "clips": clips}

    # ---------- chạy ----------
    def build(self):
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.index_paragraphs()
        (self.out / "dtbook.xml").write_text(self.dtbook(), encoding="utf-8")
        elapsed, n_par = 0.0, 0
        for g in self.groups:
            text, n = self.smil(g, elapsed)
            (self.out / f"{g}.smil").write_text(text, encoding="utf-8")
            shutil.copy(MP3_DIR / f"{g}.mp3", self.out / f"{g}.mp3")
            elapsed += self.timing[g]["duration"]
            n_par += n
        (self.out / "navigation.ncx").write_text(self.ncx(), encoding="utf-8")
        (self.out / "package.opf").write_text(self.opf(elapsed), encoding="utf-8")
        shutil.copy(ROOT / "scripts" / "resources.res", self.out / "resources.res")
        shutil.copy(ROOT / "scripts" / "dtbook.css", self.out / "dtbook.css")
        self.qa_page()

        # --- kiểm chứng ---
        dt = (self.out / "dtbook.xml").read_text(encoding="utf-8")
        ids = set(re.findall(r'\bid="([^"]+)"', dt))
        refs = re.findall(r'smilref="([^"]+)"', dt)
        bad = [r for r in refs if r.split("#par_")[-1].split("#seq_")[-1] not in ids
               and not r.split("#")[0][:-5] in self.groups]
        n_smilref_par = sum(1 for r in refs if "#par_" in r)
        ok = n_smilref_par == n_par and not bad
        print(f"Sách: {self.out.relative_to(ROOT)}  nhóm {len(self.groups)}/{len(self.timing) and len(groups_in_order(self.book))}"
              f"  tổng {clock(elapsed)}")
        print(f"Kiểm: smilref→par trong dtbook = {n_smilref_par}, <par> trong smil = {n_par}"
              f" → {'KHỚP' if ok else 'LỆCH'}; smilref hỏng: {len(bad)}")
        print(f"Mở thử: Thorium Reader → Import → {self.out / 'package.opf'}")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(Daisy(strict="--strict" in sys.argv).build())
