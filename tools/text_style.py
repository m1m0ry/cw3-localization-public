"""Shared strict display configuration and controlled font assets; no game/API dependency."""
from pathlib import Path
import hashlib
import json
import translation_contract

ROLES = {'body', 'title', 'ui', 'status'}
RUNTIME = {'CW3Localization/zh-CN.json', 'CW3Localization/font.ttf',
           'CW3Localization/serif.ttf', 'CW3Localization/text-style.json'}


def local_filename(value):
    return (isinstance(value, str) and 0 < len(value) <= 128 and not value.startswith('.')
            and value.lower().endswith(('.ttf', '.otf'))
            and not any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in '/\\:"<>|*?' for c in value))


def validate_style(path, registered=None):
    path = Path(path)
    if path.stat().st_size > 32768:
        raise ValueError('Style file exceeds 32 KiB')
    d = translation_contract.loads(path.read_text(encoding='utf8'))
    if not isinstance(d, dict) or set(d) != {'format', 'roles'} or type(d['format']) is not int or d['format'] != 1 or not isinstance(d['roles'], dict):
        raise ValueError('Style format')
    for role, style in d['roles'].items():
        if role not in ROLES or not isinstance(style, dict) or set(style) not in ({'font', 'size_percent'}, {'font', 'size_percent', 'pixel_size'}):
            raise ValueError('Style role')
        from font_registry import font_id
        filename = local_filename(style['font'])
        if not filename: font_id(style['font'])
        if registered is not None and style['font'] not in registered and not filename:
            raise ValueError('Font is not registered')
        if type(style['size_percent']) is not int or not 75 <= style['size_percent'] <= 150:
            raise ValueError('Style value')
        if type(style.get('pixel_size', 0)) is not int or not 0 <= style.get('pixel_size', 0) <= 64:
            raise ValueError('Pixel size')
    return d


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
