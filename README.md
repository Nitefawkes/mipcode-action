# MipCode PR Caller Check

Find Python callers a pull request missed when it changed a function contract. For example, if a pricing function starts requiring a `currency` keyword, MipCode can flag an unchanged caller that still omits it. Findings appear as warnings on the GitHub check. Open the check's annotations to see findings on lines outside the PR diff.

## Run on pull requests

Save this workflow as `.github/workflows/mipcode.yml`.

```yaml
name: MipCode
on: pull_request
permissions:
  contents: read

jobs:
  check-callers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: Nitefawkes/mipcode-action@fe72dc8f7ab4cb55375e268a36b0c36836b5770f # v1.0.1
```

The standard PR checkout compares the merged tree with the base commit from the event. If your workflow checks out the contributor's exact PR head instead, the Action compares it with the common ancestor of the two branches. Missing comparison history or a checkout that belongs to a different PR causes the check to fail.

| Input | Default | Behavior |
| --- | --- | --- |
| `root` | `.` | Directory within the repository to analyze. Use the repository root to include callers across packages. |
| `base-ref` | Automatic on pull requests | Supply a locally available Git commit or ref to override the comparison. Required for other events. |
| `fail-on-findings` | `false` | Warnings leave the job green. Set to `'true'` to make findings fail the job. Setup and analysis errors fail in either mode. |

This wrapper runs the static Python delta check from `coherion-mipcode==0.6.5`. It installs the hash-verified wheel from PyPI in a temporary environment. The workflow needs Git history, access to PyPI, and read access to the checked-out repository. It requires no model credentials.

[MipCode overview](https://coherion.net/mipcode) · [Public finding ledger](https://coherion.net/mipcode/ledger) · [Analyzer source](https://github.com/Nitefawkes/mipcode) · [PyPI release](https://pypi.org/project/coherion-mipcode/0.6.5/)
