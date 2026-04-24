# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.8b5] - 2026-04-23

### Changed

- Dropped support for Python 3.11, 3.12, 3.13; Python 3.14+ required
- Dropped support for Django 4.2 and 5.2; Django 6.0+ required
- Development status bumped to Beta
- Bumped dev dependencies (mypy, ruff, ty, pytest-django, pytest-cov, pre-commit, mkdocs-material, mike, hatchling) and `django-stubs` 5.2.8 → 6.0.3

### Fixed

- Documentation: `check_m2m` parameter on `is_dirty()` and `get_dirty_fields()` is a `bool`, not a dict
- Documentation: benchmark invocation path
- Documentation: `__version__` example now reflects actual version format
- Documentation: added async methods (`asave()`, `arefresh_from_db()`) and bulk helpers to the guide and API reference

### Removed

- `SECURITY.md` and `.github/ISSUE_TEMPLATE/` (GitHub issues disabled on this fork)

## [1.9.8b4] - 2026-04-06

### Added

- Async support: `asave()` and `arefresh_from_db()` overrides for dirty-tracking in async code paths
- `FIELDS_TO_CHECK_EXCLUDE` class attribute for blacklist-style field filtering (alternative to `FIELDS_TO_CHECK`)
- `capture_dirty_state()` and `reset_dirty_state()` helper functions for bulk operations (`bulk_update()` and similar)

### Changed

- Tests synced with upstream django-dirtyfields v1.9.9 (F() expression auto-refresh behavior on Django 6.0, deterministic timezone tests)

## [1.9.8b3] - 2026-01-22

### Changed

- Performance: `__get__` uses try/except for faster dict access
- Performance: `__set__` has early returns and caches `FIELDS_TO_CHECK` per instance
- Performance: `_values_equal` has a fast path for same-type comparisons
- Performance: `_normalize_value` uses shallow copy for simple dicts/lists (common for JSONField)
- Benchmarks diversified across DateTime, Decimal, JSON, Float, and Text fields

## [1.9.8b2] - 2026-01-17

### Added

- Django 4.2 LTS, 5.2, and 6.0 support
- Python 3.11 and 3.12 support
- Python 3.14t (free-threaded) support

### Changed

- Minimum Python version is now 3.11 (from 3.13)
- Minimum Django version is now 4.2 LTS (from 5.1)

## [1.9.8b1] - 2025-01-17

### Added

- Re-added M2M field tracking with `ENABLE_M2M_CHECK` class attribute
- Re-added `check_m2m` parameter to `is_dirty()` and `get_dirty_fields()`
- Re-added custom `compare_function` support for field value comparison
- Re-added custom `normalise_function` support for output value transformation
- Added `was_dirty()` and `get_was_dirty_fields()` methods
- Added `raw_compare`, `normalise_value`, and `timezone_support_compare` utility functions

### Changed

- Version numbering now follows upstream django-dirtyfields for API compatibility indication

## [0.1.0a2] - 2025-01-16

### Changed

- Test automated PyPI publishing pipeline

## [0.1.0a1] - 2025-01-16

### Added

- Initial release as `django-filthyfields` (fork of `django-dirtyfields`)
- Descriptor-based dirty field tracking (replaces signal-based approach)
- Support for `FIELDS_TO_CHECK` to limit tracked fields
- File field tracking including `.save()` and `.delete()` methods
- F() expression support
- Modern Python 3.13+ and Django 5.0+ support

### Changed

- Complete rewrite using descriptors instead of `post_init`/`post_save` signals
- Significantly improved performance for model loading

### Removed

- Python < 3.13 support
- Django < 5.0 support

---

## Historical Releases (from upstream django-dirtyfields)

## [1.9.8] - 2025-11-17

### Added

- Confirm support for Python 3.14
- Confirm support for Django 5.2

### Removed

- Drop support for Python 3.9
- Drop support for Django 2.2, 3.0, 3.1

## [1.9.7] - 2025-03-22

### Fixed

- Fix `Model.refresh_from_db()` so calling it with 3 positional args works.

## [1.9.6] - 2025-02-07

### Fixed

- Allow passing `from_queryset` argument to `Model.refresh_from_db()` in Django 5.1+

## [1.9.5] - 2024-11-09

### Fixed

- Fixed error in PyPI publish process

## [1.9.4] - 2024-11-09

### Added

- Confirm support for Python 3.13
- Confirm support for Django 5.1

### Removed

- Drop support for Python 3.8

## [1.9.3] - 2024-05-24

### Added

- Confirm support for Python 3.12
- Confirm support for Django 5.0

### Removed

- Drop support for Python 3.7
- Drop support for Django 2.0, 2.1

## [1.9.2] - 2023-04-12

### Added

- Confirm support for Django 4.2

## [1.9.1] - 2023-01-14

### Fixed

- Fixed a `KeyError` that would occur when updating a field two times in a row when the field value is set to an `F` object and the field is specified in the `update_fields` argument to `save()`. (#209)

## [1.9.0] - 2022-11-07

### Added

- Confirm support for Python 3.11
- Confirm support for Django 4.1

### Changed

- The method `get_dirty_fields()` now returns only the file name for FileFields. This is to improve performance, since the entire `FieldFile` object will no longer be copied when Model instances are initialized and saved. (#203)

### Fixed

- The method `save_dirty_fields()` can now be called on Model instances that have not been saved to the Database yet. In this case all fields will be considered dirty, and all will be saved to the Database. Previously doing this would result in an Exception being raised. (#200)

### Removed

- Drop support for Django 1.11

## [1.8.2] - 2022-07-16

### Documentation

- General improvements to content and generation of Documentation (#197).

## [1.8.1] - 2022-03-07

### Documentation

- Document limitations when using dirtyfields and database transactions (#148).
- Document how to use a Proxy Model to avoid performance impact (#132).

## [1.8.0] - 2022-01-22

### Added

- Confirm support of Python 3.10
- Confirm support of Django 4.0

### Changed

- Run CI tests on Github Actions since travis-ci.org has been shutdown.

### Removed

- Drop support for Python 3.6

## [1.7.0] - 2021-05-02

### Added

- Provide programmatically accessible package version number. Use `dirtyfields.__version__` for a string, `dirtyfields.VERSION` for a tuple.
- Build and publish a wheel to PyPI.

### Changed

- Only look at concrete fields when determining dirty fields.
- Migrate package metadata from setup.py to setup.cfg and specify the PEP-517 build-backend to use with the project.

### Fixed

- Fixed a `KeyError` that happened when saving a Model with `update_fields` specified after updating a field value with an `F` object (#118).

## [1.6.0] - 2021-04-07

### Added

- Confirm support of Django 3.2

### Changed

- Remove pytz as a dependency.

## [1.5.0] - 2021-01-15

### Added

- Confirm support of Python 3.8
- Confirm support of Python 3.9
- Confirm support of Django 3.0
- Confirm support of Django 3.1

### Removed

- Drop support of Python 2.7
- Drop support of Python 3.5

## [1.4.1] - 2020-11-28

### Fixed

- Fixes an issue when `refresh_from_db` was called with the `fields` argument, the dirty state for all fields would be reset, even though only the fields specified are reloaded from the database. Now only the reloaded fields will have their dirty state reset (#154).
- Fixes an issue where accessing a deferred field would reset the dirty state for all fields (#154).

## [1.4] - 2020-04-11

### Added

- Confirm support of Python 3.7
- Confirm support of Django 2.0, 2.1, 2.2

### Fixed

- Fixes tests for Django 2.0
- `refresh_from_db` is now properly resetting dirty fields.
- Adds `normalise_function` to provide control on how dirty values are stored

### Removed

- Drop support of Python 3.4
- Drop support of Django 1.8, 1.9, 1.10

## [1.3.1] - 2018-02-28

### Added

- Updates python classifier in setup file (#116). Thanks amureki.
- Adds PEP8 validation in travisCI run (#123). Thanks hsmett.

### Fixed

- Avoids `get_deferred_fields` to be called too many times on `_as_dict` (#115). Thanks benjaminrigaud.
- Respects `FIELDS_TO_CHECK` in `reset_state` (#114). Thanks bparker98.

## [1.3] - 2017-08-23

### Added

- Add test coverage for Django 1.11.
- A new attribute `FIELDS_TO_CHECK` has been added to `DirtyFieldsMixin` to specify a limited set of fields to check.

### Fixed

- Fixes issue with verbose mode when the object has not been yet saved in the database (MR #99). Thanks vapkarian.
- Correctly handle `ForeignKey.db_column` `{}_id` in `update_fields`. Thanks Hugo Smett.
- Fixes #111: Eliminate a memory leak.
- Handle deferred fields in `update_fields`

### Removed

- Drop support for unsupported Django versions: 1.4, 1.5, 1.6 and 1.7 series.

## [1.2.1] - 2016-11-16

### Added

- `django-dirtyfields` is now tested with PostgreSQL, especially with specific fields

### Fixed

- Fixes #80: Use of `Field.rel` raises warnings from Django 1.9+
- Fixes #84: Use `only()` in conjunction with 2 foreign keys triggers a recursion error
- Fixes #77: Shallow copy does not work with Django 1.9's JSONField
- Fixes #88: `get_dirty_fields` on a newly-created model does not work if pk is specified
- Fixes #90: Unmark dirty fields only listed in `update_fields`

## [1.2] - 2016-08-11

### Added

- `django-dirtyfields` is now compatible with Django 1.10 series (deferred field handling has been updated).

## [1.1] - 2016-08-04

### Added

- A new attribute `ENABLE_M2M_CHECK` has been added to `DirtyFieldsMixin` to enable/disable m2m check functionality. This parameter is set to `False` by default.

!!! warning "Breaking Change"
    Backward incompatibility with v1.0.x series. If you were using `check_m2m` parameter to check m2m relations, you should now add `ENABLE_M2M_CHECK = True` to these models inheriting from `DirtyFieldsMixin`.

## [1.0.1] - 2016-07-25

### Fixed

- Fixing a bug preventing `django-dirtyfields` to work properly on models with custom primary keys.

## [1.0] - 2016-06-26

After several years of existence, django-dirty-fields is mature enough to switch to 1.X version.

### Changed

- `get_dirty_fields` is now more consistent for models not yet saved in the database. `get_dirty_fields` is, in that situation, always returning ALL fields, where it was before returning various results depending on how you initialised your model.

!!! warning "Breaking Change"
    It may affect you specially if you are using `get_dirty_fields` in a `pre_save` receiver. See more details at https://github.com/romgar/django-dirtyfields/issues/65.

### Added

- Adding compatibility for old _meta API, deprecated in Django 1.10 version and now replaced by an official API.
- General test cleaning.

## [0.9] - 2016-06-18

### Added

- Adding Many-to-Many fields comparison method `check_m2m` in `DirtyFieldsMixin`.
- Adding `verbose` parameter in `get_dirty_fields` method to get old AND new field values.

## [0.8.2] - 2016-03-19

### Added

- Adding field comparison method `compare_function` in `DirtyFieldsMixin`.
- Also adding a specific comparison function `timezone_support_compare` to handle different Datetime situations.

## [0.8.1] - 2015-12-08

### Fixed

- Not comparing fields that are deferred (`only` method on `QuerySet`).
- Being more tolerant when comparing values that can be on another type than expected.

## [0.8] - 2015-10-30

### Added

- Adding `save_dirty_fields` method to save only dirty fields in the database.

## [0.7] - 2015-06-18

### Added

- Using `copy` to properly track dirty fields on complex fields.
- Using `py.test` for tests launching.

## [0.6.1] - 2015-06-14

### Fixed

- Preventing django db expressions to be evaluated when testing dirty fields (#39).

## [0.6] - 2015-06-11

### Added

- Using `to_python` to avoid false positives when dealing with model fields that internally convert values (#4)

### Fixed

- Using `attname` instead of `name` on fields to avoid massive useless queries on ForeignKey fields (#34). For this kind of field, `get_dirty_fields()` is now returning instance id, instead of instance itself.

## [0.5] - 2015-05-06

### Added

- Adding code compatibility for python3
- Launching travis-ci tests on python3
- Using `tox` to launch tests on Django 1.5, 1.6, 1.7 and 1.8 versions
- Updating `runtests.py` test script to run properly on every Django version.

### Fixed

- Catching `Error` when trying to get foreign key object if not existing (#32).

## [0.4.1] - 2015-04-08

### Fixed

- Removing `model_to_form` to avoid bug when using models that have `editable=False` fields.

## [0.4] - 2015-03-31

### Added

- Adding `check_relationship` parameter on `is_dirty` and `get_dirty_field` methods to also check foreign key values.
