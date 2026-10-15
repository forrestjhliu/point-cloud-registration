from pathlib import Path
from zipfile import ZipFile
import json
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps, ImageDraw

root = Path(__file__).resolve().parent
for stem in ['low_overlap_registration_6slides']:
    with ZipFile(root / (stem + '.pptx')) as z:
        slide_paths = sorted(n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n))
        note_paths = sorted(n for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml', n))
        assert len(slide_paths) == 6 and len(note_paths) == 6
        for n in slide_paths + note_paths:
            ET.fromstring(z.read(n))
        images = [n for n in z.namelist() if n.startswith('ppt/media/')]
        assert images
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
        slide_text = {
            str(i): [t.text for t in ET.fromstring(z.read(f'ppt/slides/slide{i}.xml')).findall('.//a:t', ns)]
            for i in range(1, 7)
        }
        before_path = root / 'slides_before_dataset_explanation.json'
        if before_path.exists():
            before = json.loads(before_path.read_text(encoding='utf-8'))
            for i in [1, 3, 6]:
                assert slide_text[str(i)] == before[str(i)], f'Unrelated slide {i} changed'
        all_text = '\n'.join(t for lines in slide_text.values() for t in lines if t)
        assert not re.search(r'项目\s*[AB]|Project\s*[AB]\b', all_text, flags=re.I)
        print(stem, {'slides': len(slide_paths), 'speaker_notes': len(note_paths), 'embedded_images': len(images)})
    files = sorted((root / 'previews' / stem).glob('*.PNG'))
    assert len(files) == 6
    contact = Image.new('RGB', (1600, 1350), '#DCE4E9')
    for i, p in enumerate(files):
        im = Image.open(p).convert('RGB')
        assert im.size == (1600, 900)
        im = im.resize((800, 450), Image.Resampling.LANCZOS)
        contact.paste(im, ((i % 2) * 800, (i // 2) * 450))
    contact.save(root / 'previews' / (stem + '_overview.jpg'), quality=94)

assert json.loads((root / 'layout_check.json').read_text(encoding='utf-8-sig')) == []
examples_root = root / 'assets/registration/two_examples'
manifest = json.loads((examples_root / 'examples.json').read_text(encoding='utf-8'))
assert manifest['reference_identical_between_examples']
assert (examples_root / 'high_3dmatch/input_reference.png').read_bytes() == (examples_root / 'low_3dlomatch/input_reference.png').read_bytes()
print('New sample downloads:', manifest['downloaded_range_bytes'], 'bytes; full archive not downloaded.')
print('All 6 slide XML files, notes, embedded images and zero-overflow checks passed.')
