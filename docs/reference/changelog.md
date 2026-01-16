# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

- M2M field tracking (`ENABLE_M2M_CHECK`) - may be re-added
- Custom `compare_function` - may be re-added
- Python < 3.13 support
- Django < 5.0 support
