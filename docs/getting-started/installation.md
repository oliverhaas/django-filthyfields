# Installation

## Requirements

- Python 3.14+
- Django 6.0+

## Install with pip

```bash
pip install django-filthyfields
```

## Install with uv

```bash
uv add django-filthyfields
```

## Verify Installation

```python
>>> from filthyfields import DirtyFieldsMixin
>>> DirtyFieldsMixin
<class 'filthyfields.filthyfields.DirtyFieldsMixin'>
```

!!! note "Import Path"
    The PyPI distribution is `django-filthyfields`; the import package is `filthyfields`.
