"""Controlled static font validation for development builds."""
from pathlib import Path
import hashlib


def validate_font(path, family, expected=None):
    from fontTools.ttLib import TTFont
    path = Path(path)
    if path.stat().st_size > 50_000_000:
        raise ValueError('Font exceeds 50 MB')
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Font hash differs from controlled build')
    if family not in ('sans','serif'):raise ValueError('Unknown controlled family')
    prefix = 'CW3 ' + ('Sans' if family == 'sans' else 'Serif') + ' SC External'
    with TTFont(path) as font:
        if 'fvar' in font or not any(n.toUnicode().startswith(prefix) for n in font['name'].names if n.nameID in (1, 16)):
            raise ValueError('Expected controlled static font family')
        return set(font.getBestCmap())
