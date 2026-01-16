# Installation

## Requirements

- Python 3.13+
- Django 5.0+

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
>>> from dirtyfields import DirtyFieldsMixin
>>> DirtyFieldsMixin
<class 'dirtyfields.dirtyfields.DirtyFieldsMixin'>
```

!!! note "Import Path"
    The package is installed as `django-filthyfields` but you import from `dirtyfields`.
    This maintains compatibility with the original django-dirtyfields package.
