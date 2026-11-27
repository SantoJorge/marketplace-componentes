"""Executed in the independent HorizonCut environment, not Django's venv."""
import json
import sys
from pathlib import Path
from PIL import Image, ImageOps
from rembg import remove, new_session


def main():
    jobs = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    session = new_session('u2net', providers=['CPUExecutionProvider'])
    failed = 0
    for job in jobs:
        try:
            with Image.open(job['source']) as source:
                image = ImageOps.exif_transpose(source).convert('RGBA')
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            result = remove(image, session=session).convert('RGBA')
            alpha = result.getchannel('A')
            low, high = alpha.getextrema()
            if low >= 250 or high < 64:
                raise ValueError('Mascara sin transparencia util')
            bbox = alpha.point(lambda v: 255 if v > 12 else 0).getbbox()
            if not bbox:
                raise ValueError('Recorte vacio')
            result = ImageOps.expand(result.crop(bbox), border=5, fill=(0, 0, 0, 0))
            output = Path(job['output'])
            temp_output = output.with_suffix('.tmp')
            result.save(temp_output, format='PNG', optimize=True)
            temp_output.replace(output)
            print('RECORTE OK:', job['id'], flush=True)
        except Exception as exc:
            failed += 1
            print('RECORTE FALLIDO:', job['id'], str(exc), flush=True)
    return 1 if failed else 0

if __name__ == '__main__':
    sys.exit(main())
