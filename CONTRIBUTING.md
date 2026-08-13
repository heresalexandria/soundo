# Contributing to Soundslo

Contributions are welcome through issues and pull requests.

## Development checks

```bash
uv sync --dev
uv run ruff check .
uv run pytest
uv build
```

Keep generated audio, downloaded model weights, local databases, virtual environments, and
runtime checkouts out of commits. The existing `.gitignore` covers their standard locations.

## Contribution license

By submitting a contribution, you represent that you have the right to submit it and agree that
it is provided under the repository's MIT License. Do not submit model weights, training data,
audio, source code, or other material unless its license permits inclusion and redistribution
under the applicable repository terms.

Do not modify or remove `LICENSE`, `NOTICE`, the files in `licenses/`, or the visible
“Powered by Stability AI” attribution without first checking the applicable third-party terms.
