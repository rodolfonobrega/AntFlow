# Releasing to PyPI

This repository is configured to publish to PyPI automatically when a GitHub Release is published.

## One-time setup

### 1. Create the GitHub environment

In GitHub, go to `Settings -> Environments` and create an environment named `pypi`.

Required protection:

- Require manual approval on each run for the `pypi` environment

Recommended protections:

- Restrict deployment to tags that match `v*`
- Add required reviewers so only trusted maintainers can approve the publish job

### 2. Register the trusted publisher on PyPI

If the `AntFlow` project already exists on PyPI:

1. Open the project on PyPI
2. Go to `Manage -> Publishing`
3. Add a GitHub Actions trusted publisher with:
   - Owner: `rodolfonobrega`
   - Repository name: `AntFlow`
   - Workflow name: `pypi.yml`
   - Environment name: `pypi`

If the project does not exist on PyPI yet:

1. Open `https://pypi.org/manage/account/publishing/`
2. Add a pending GitHub Actions publisher with the same values above
3. Set the PyPI project name to `AntFlow`

## Release flow

### Option A: Use the release script

Run:

```bash
./scripts/release.sh 0.7.3
```

The script updates the version in `pyproject.toml` and `antflow/_version.py`, commits, pushes, creates the `v0.7.3` tag, pushes the tag, and publishes the GitHub Release.

### Option B: Manual release

1. Update `project.version` in `pyproject.toml`
2. Update `__version__` in `antflow/_version.py`
3. Commit and push the version change
4. Create a Git tag that matches the version, for example `v0.7.3`
5. Publish a GitHub Release for that tag

When the release is published, `.github/workflows/pypi.yml` will:

- verify that the GitHub release tag matches `project.version`
- build the sdist and wheel
- publish the generated files to PyPI using Trusted Publishing

## Notes

- No PyPI token needs to be stored in GitHub Secrets
- The workflow depends on GitHub Release publication, not only on pushing a tag
- If the tag and `project.version` differ, the workflow will fail before uploading anything
