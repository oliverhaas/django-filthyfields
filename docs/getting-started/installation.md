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
<class 'dirtyfields.dirtyfields.DirtyFieldsMixin'>
```

!!! note "Import Path"
    The package is installed as `django-filthyfields` but you import from `dirtyfields`.
    This maintains compatibility with the original django-dirtyfields package.
