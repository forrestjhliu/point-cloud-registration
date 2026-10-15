"""Check the published PowerPoint/PDF and render the PDF used for delivery."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import hashlib
import json
import posixpath
import re
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
PUBLISHED = ROOT.parent
STEM = "low_overlap_registration_proposal"
ASSETS = PUBLISHED / "v2/assets/registration/two_examples"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pixels(data):
    with Image.open(BytesIO(data)) as im:
        rgb = im.convert("RGB")
        return rgb.size, digest(rgb.tobytes())


plan = json.loads((ROOT / "slide_plan.json").read_text(encoding="utf-8-sig"))
assert len(plan) == 12
assert all(1 <= len(p["key_points"]) <= 3 for p in plan)
assert json.loads((ROOT / "layout_check.json").read_text(encoding="utf-8-sig")) == []

for suffix in ("pptx", "pdf"):
    assert (ROOT / f"{STEM}.{suffix}").read_bytes() == (PUBLISHED / f"{STEM}.{suffix}").read_bytes()

with ZipFile(PUBLISHED / f"{STEM}.pptx") as z:
    slides = [n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
    notes = [n for n in z.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
    assert len(slides) == len(notes) == 12
    report = []
    for i in range(1, 13):
        slide_xml = ET.fromstring(z.read(f"ppt/slides/slide{i}.xml"))
        visible = "\n".join(t.text or "" for t in slide_xml.findall(".//a:t", NS))
        assert not re.search(r"项目\s*[AB]|Project\s*[AB]\b", visible, re.I)
        assert "http" not in visible, "Sources belong in notes"
        assert len(visible) < 260, (i, len(visible))
        note_xml = ET.fromstring(z.read(f"ppt/notesSlides/notesSlide{i}.xml"))
        note_text = "\n".join(t.text or "" for t in note_xml.findall(".//a:t", NS))
        assert len(note_text) > 200 and "技术备注" in note_text and "https://" in note_text
        report.append({"page": i, "key_points": len(plan[i - 1]["key_points"]), "visible_characters": len(visible)})

    # Match the three illustrations on each example page to the actual data rasters.
    for i, group in [(1, "high_3dmatch"), (4, "low_3dlomatch")]:
        rel_xml = ET.fromstring(z.read(f"ppt/slides/_rels/slide{i}.xml.rels"))
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in rel_xml}
        slide_xml = ET.fromstring(z.read(f"ppt/slides/slide{i}.xml"))
        embedded = []
        for blip in slide_xml.findall(".//a:blip", NS):
            rel_id = blip.attrib[f"{{{NS['r']}}}embed"]
            path = posixpath.normpath(posixpath.join("ppt/slides", rels[rel_id]))
            embedded.append(pixels(z.read(path)))
        assert len(embedded) == 3
        for filename in ["input_source.png", "input_reference.png", "gt_common_surface.png"]:
            assert pixels((ASSETS / group / filename).read_bytes()) in embedded, (i, filename)

pdf = PUBLISHED / f"{STEM}.pdf"
info = subprocess.check_output(["pdfinfo", str(pdf)], text=True, encoding="utf-8", errors="replace")
assert re.search(r"Pages:\s+12\b", info), info
render_dir = ROOT / "previews/published_pdf"
render_dir.mkdir(parents=True, exist_ok=True)
subprocess.run(["pdftoppm", "-png", "-scale-to-x", "1600", "-scale-to-y", "900", str(pdf), str(render_dir / "slide")], check=True, capture_output=True)
files = sorted(render_dir.glob("slide-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
assert len(files) == 12
overview = Image.new("RGB", (1920, 1440), "#dce4e9")
for i, path in enumerate(files):
    with Image.open(path) as im:
        assert im.size == (1600, 900)
        thumb = im.convert("RGB").resize((640, 360), Image.Resampling.LANCZOS)
    overview.paste(thumb, ((i % 3) * 640, (i // 3) * 360))
overview.save(ROOT / "previews/published_pdf_overview.jpg", quality=95)
overview.save(PUBLISHED / "previews/low_overlap_registration_proposal_overview.jpg", quality=95)
(ROOT / "verification.json").write_text(json.dumps({"slides": report, "pdf_pages": 12, "example_images_match_actual_data": True, "published_files_match_source": True}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
print("Verified: 12 slides and notes; 1-3 key points/page; zero text overflow; 6 genuine data panels; published PDF rendered and matched.")
