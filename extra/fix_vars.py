import sys

def fix_file(f, replacements):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    for o, n in replacements:
        content = content.replace(o, n)
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

fix_file('main.py', [
    ('rahul ai = RahulLive(', 'rahul_ai = RahulLive('),
    ('rahul ai.plugin_manager', 'rahul_ai.plugin_manager'),
    ('plugin_manager.register_rahul(rahul ai)', 'plugin_manager.register_rahul(rahul_ai)'),
    ('plugin_manager.dispatch("on_startup", rahul ai)', 'plugin_manager.dispatch("on_startup", rahul_ai)'),
    ('asyncio.run(rahul ai.run())', 'asyncio.run(rahul_ai.run())')
])

fix_file('plugin_manager.py', [
    ('self.rahul ai', 'self.rahul_ai'),
    ('rahul ai=self.rahul_ai', 'rahul_ai=self.rahul_ai')
])

print('Fixes applied!')
