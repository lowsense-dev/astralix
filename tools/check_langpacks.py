# © LowSense, 2026 · astralix Userbot · GNU AGPLv3
"""Check changed translations without grandfathering new placeholder/HTML errors."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import string
import subprocess

from ruamel.yaml import YAML


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in {'img', 'br', 'hr', 'input', 'source', 'wbr'}:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError(f'Unbalanced HTML tag: {tag}')

    def close(self):
        super().close()
        if self.stack:
            raise ValueError(f'Unclosed HTML tags: {self.stack}')


def flatten(data):
    return {(group, key): value for group, strings in data.items() if isinstance(strings, dict)
            for key, value in strings.items() if isinstance(value, str)}


def check(base):
    packs, changed = {}, set()
    for language in ('en', 'ru'):
        path = f'astralix/langpacks/{language}.yml'
        packs[language] = flatten(YAML(typ='safe').load(Path(path).read_text()))
        previous = flatten(YAML(typ='safe').load(subprocess.check_output(['git', 'show', f'{base}:{path}'])))
        changed.update(key for key in packs[language].keys() | previous.keys()
                       if packs[language].get(key) != previous.get(key))
    for key in sorted(changed):
        if all(key not in pack for pack in packs.values()):
            continue
        fields = []
        for language, pack in packs.items():
            if key not in pack:
                raise ValueError(f'{language}: missing {key}')
            template = pack[key]
            fields.append(sorted(field for _, field, _, _ in string.Formatter().parse(template) if field is not None))
            parser = Markup()
            parser.feed(template)
            parser.close()
        if fields[0] != fields[1]:
            raise ValueError(f'Placeholder mismatch in {key}: {fields}')
    print(f'Validated {len(changed)} changed language keys')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='HEAD^')
    check(parser.parse_args().base)
