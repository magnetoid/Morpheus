import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings')
django.setup()

from api.schema import get_schema  # noqa: E402 — deliberate late import

schema = get_schema()
print('QUERY FIELDS:', [f.name for f in schema.get_type_by_name('Query').fields])
print('MUTATION FIELDS:', [f.name for f in schema.get_type_by_name('Mutation').fields])
