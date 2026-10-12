"""Reproduce the controlled OFL Serif subset for the translation dictionary."""
from pathlib import Path
import argparse, hashlib, json
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    provenance = json.loads((ROOT/'fonts/serif-provenance.json').read_text())
    assert hashlib.sha256(a.source.read_bytes()).hexdigest() == provenance['source_sha256']
    assert not a.output.exists(), 'Keep existing font evidence'
    keep = set(json.loads((ROOT/'fonts/codepoints.json').read_text()))
    font = TTFont(a.source, recalcTimestamp=False)
    sub = subset.Subsetter(); sub.populate(unicodes=keep); sub.subset(font)
    font = instantiateVariableFont(font, {'wght': 400}, inplace=True)
    family = 'CW3 Serif SC External ' + provenance['source_sha256'][:12]
    for platform, encoding, language in sorted({(n.platformID,n.platEncID,n.langID) for n in font['name'].names} | {(3,1,0x409),(1,0,0)}):
        for id, name in [(1,family),(2,'Regular'),(3,family+' Regular'),(4,family+' Regular'),(6,'CW3SerifSCExternal-'+provenance['source_sha256'][:12]),(16,family),(17,'Regular')]:
            font['name'].setName(name,id,platform,encoding,language)
    font['head'].modified = provenance['subset_head_modified']
    font['OS/2'].fsType = 0
    a.output.parent.mkdir(parents=True,exist_ok=True); font.save(a.output)
    assert 'fvar' not in font and keep <= set(font.getBestCmap())
    print('Controlled static Serif weight 400; covered', len(keep), 'codepoints; SHA256',hashlib.sha256(a.output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
