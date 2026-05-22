from pathlib import Path
import re

paths = [
    'README.md',
    'backend/api/main.py',
    'backend/db/database.py',
    'backend/spiders/spiders.py',
    'frontend/src/App.vue',
    'scripts/check_platform_consistency.py',
]
secret_patterns = [
    re.compile(r'(api_key|secret|password|token|passwd)\s*[:=]\s*["\'][^"\']{6,}["\']', re.I),
    re.compile(r'Bearer\s+[A-Za-z0-9._~+/=-]{10,}'),
    re.compile(r'access_token=(?!YOUR_TOKEN)[A-Za-z0-9._~+/=-]{6,}', re.I),
    re.compile(r'hook/(?!YOUR_TOKEN)[A-Za-z0-9_-]{6,}', re.I),
]
danger_patterns = [
    re.compile(r'os\.system\('),
    re.compile(r'subprocess.*shell=True'),
    re.compile(r'\beval\('),
    re.compile(r'\bexec\('),
    re.compile(r'pickle\.loads?\('),
    re.compile(r'execute\(f"'),
    re.compile(r'\.format\(.*SELECT'),
    re.compile(r'\.format\(.*INSERT'),
]
secret_hits = []
danger_hits = []
for path in paths:
    text = Path(path).read_text(errors='ignore')
    for i, line in enumerate(text.splitlines(), 1):
        if any(p.search(line) for p in secret_patterns):
            if 'YOUR_PASSWORD' not in line and 'YOUR_TOKEN' not in line and 'Bearer ***' not in line:
                secret_hits.append((path, i, line.strip()))
        if any(p.search(line) for p in danger_patterns):
            danger_hits.append((path, i, line.strip()))

readme = Path('README.md').read_text()
print('secret_hits', secret_hits)
print('danger_hits', danger_hits)
print('closed_auth_count', readme.count('-H "Authorization: Bearer ***"'))
print('unclosed_auth_count', readme.count('-H "Authorization: Bearer ***\n'))
print('webhook_placeholders', 'hook/YOUR_TOKEN' in readme and 'access_token=YOUR_TOKEN' in readme)
print('no_secret_key_claim', 'SECRET_KEY' not in readme)
raise SystemExit(1 if secret_hits or danger_hits else 0)
