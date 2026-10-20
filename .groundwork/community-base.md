# Building a base of decisions from groundwork

A community, such as the teams of an organisation, can build from groundwork a base of decisions of its own, which its projects synchronise on a voluntary basis. The base is itself a project of groundwork: it follows groundwork with the update script, and its projects follow it with the same script. A change of groundwork reaches a project in two pull requests, the first on the base and the second on the project, once the base has published a version.

This page tells what a community does. The rules are in [ADR 0001](../docs/adr/0001-record-architecture-decisions.md) (the numbers), in [ADR 1000](https://github.com/michelwils/groundwork/blob/main/docs/adr/1000-choosing-the-adrs-a-project-synchronises.md) (the choice of a project) and in [`.groundwork/practices.md`](practices.md) (the map of the practices). The scripts that this page names are the ones every project has: [`update_groundwork.py`](scripts/update_groundwork.py) and [`open_update_pull_request.py`](scripts/open_update_pull_request.py).

## The three zones of the numbers

- `0001` to `0999` are reserved for groundwork. No project and no base numbers an ADR of its own there.
- A base reserves more ranges of its own, in the file `.groundwork-ranges`, so that its projects receive its decisions. A project does not touch an ADR in a range that its source reserves.
- Every other number is free. The ADRs of a project, and the ADRs of the base that are not for its projects, are numbered there.

## Start a base

1. **Create the repository from the template** of groundwork, rather than forking it. A repository created from a template starts with one commit and does not carry the history of groundwork; a fork carries it. The documentation of GitHub does not say what a fork does with the tags, and the projects of the base read the tags of the base, so check that a fork has no tag `vX.Y.Z` of groundwork before it publishes its own versions.
2. **Adopt groundwork like any project**, following [Adopting groundwork](https://github.com/michelwils/groundwork#adopting-groundwork): apply the settings, replace the README, adjust the license as [the last section](#the-license) tells, create the secret `GROUNDWORK_UPDATE_TOKEN`, and record in `.groundwork-version` the version of groundwork the base starts from.
3. **Choose what to keep** of groundwork. Without a file, the base keeps everything. To drop ADRs, list the ones to keep in `.groundwork-adrs`, one number or range per line: ADR 0001 stays, and so do the ADRs that the ones listed need. The update does not delete anything for ADRs that are left out: run [`apply_choice.py`](scripts/apply_choice.py) on a branch, which deletes their files and their blocks and keeps what you changed, and see its `--dry-run` first. Its projects can only choose among what the base holds.
4. **Reserve the ranges** in `.groundwork-ranges`, one `NNNN-NNNN` per line (bounds included, the first not above the second, `#` for a comment). A range may not overlap `0001-0999` or another range, and a line that is not a range is refused by the checks. `9000` to `9999` is a suggestion, not a default: any range will do that lies above the numbers the projects already use, since a range cannot be reserved over an ADR that exists.
5. **Write the ADRs of the base** in its ranges, from the first number of the range and without skipping one, with the template of groundwork. An ADR of the base may need an ADR of groundwork, never the reverse.
6. **Add to the map** an entry in `.groundwork/practices.md` for each ADR of a range: the ADRs it needs, the files that apply it, and the files where its lines are, in blocks delimited by `<!-- groundwork:9000 -->` and `<!-- /groundwork -->` (or `# groundwork:9000` and `# /groundwork` in YAML). Put the entries before the entry of ADR 0001, where groundwork does not write.
7. **Set the variable `GROUNDWORK_SOURCE` to `true`** in the settings of the repository (`gh variable set GROUNDWORK_SOURCE --body true`). The base then runs the test that builds, from its own files, the tree of a project for each ADR left out and checks it. The variable is not synchronised, so each repository decides for itself.
8. **Publish a version** with the `release` workflow, and make the repository a template repository in its settings, so that the projects are created from it.

## Follow groundwork

The workflow `update-groundwork` of the base opens a pull request `chore: update groundwork to vX.Y.Z` to the latest version of groundwork when there is a later one than the base follows, as a draft if files are in conflict.

- Review it as any change: if the base has a choice, the pull request says which ADRs enter it because an ADR it keeps needs them.
- **Change its title before the merge.** A `chore` does not change the version, and the release workflow publishes nothing for it, so the projects would not see the change. Use `fix:` or `feat:` according to the effect on the projects, and `feat!:` if it makes them change something.
- Conflicts come when both sides change lines that are close. The entries of the base placed before the entry of ADR 0001, and its blocks placed away from the lines that groundwork changes, do not conflict with the entries and the lines that groundwork adds.
- Publish a version once the pull request is merged. The numbers of the versions of the base and of groundwork have nothing in common: `.groundwork-version` of the base holds a version of groundwork, and that of a project a version of the base.

## In a project of the base

- Create the repository from the template of the base. It inherits the files that the base recorded for itself: delete `.groundwork-version` and, if the base has them, `.groundwork-adrs` and `.groundwork-source` (`git rm` fails on a file that is missing, so name only the ones that exist), or the adoption takes the project for one that has already adopted. Then adopt groundwork like any project, following [Adopting groundwork](https://github.com/michelwils/groundwork#adopting-groundwork), with `--source` set to the address of the base: `apply_choice.py` records the version of the base, the choice and the source.
- **Record the base as the source of the updates.** `apply_choice.py --source` writes `.groundwork-source` at the root of the project, with one line, the address of the base: `https://host/path`. Without it the project follows groundwork, whose address is the default. The update, and the weekly workflow, read the file, and `--source` still wins for a run by hand. The file is never copied from the base, which therefore cannot overwrite it. A base that follows groundwork needs no such file, and one that follows another base has its own.
- **A private base needs a credential that can read it.** The weekly workflow fetches the base with the credential of the repository of the project, which is limited to that repository. GitHub's documentation does not say whether the credential kept by the checkout applies to another repository, so grant the token `GROUNDWORK_UPDATE_TOKEN` read access to the contents of the base as well, and look at the first run.
- The project takes everything that the base reserves, groundwork's `0001` to `0999` that the base kept and the ranges of the base, or chooses with `.groundwork-adrs`. The update copies neither `.groundwork-version` nor `.groundwork-adrs` of the base to it; the template does, hence the first step.
- The project numbers its own ADRs from the first number that no range of the base reserves, and may use any number that no range reserves.

## The own decisions of the base

The ADRs of groundwork numbered `1000` or more are its own decisions and are not synchronised, but a repository created from the template holds them. The base deletes them, or keeps [ADR 1000](https://github.com/michelwils/groundwork/blob/main/docs/adr/1000-choosing-the-adrs-a-project-synchronises.md), which explains the choice that it implements. Its own decisions, the ones that are not for its projects, are then numbered from `1000` if it deleted them all, or from `1001` if it kept ADR 1000. If a range of the base lies at `1000` or above, they start at the first number that no range reserves.

## The license

groundwork is under the MIT license, which asks that "the above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software". A base keeps the file `LICENSE` with the line of groundwork and adds its own line below it. This is a practice, not a legal opinion. The update never copies `LICENSE` to a project.
