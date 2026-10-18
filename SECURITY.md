# Security policy

## Reporting a vulnerability

Report a vulnerability privately: open the Security tab of this repository, then Advisories, then "Report a vulnerability". Do not open a public issue or a pull request, since they would disclose the vulnerability before it is fixed.

## Handling a report

The maintainer handles a report in the private advisory, and nothing is public until the fix is merged in step 3. The steps are written for a single maintainer, and any project can copy them.

1. **Confirm.** Answer in the advisory, reproduce the fault, estimate its severity and list the versions it touches.
2. **Prepare the fix.** In the advisory, create the temporary private fork. Write there the test of the case first, then the fix. Neither the CI nor the status checks run in the fork: run the checks and the tests on your machine, as the [README](README.md#checks) says, and write in the advisory that you did.
3. **Merge.** The ruleset of the default branch requires the `checks` status, which the fork can never report, so the merge from the advisory stays blocked. Disable the ruleset in the settings of the repository, merge the pull request from the advisory, then enable the ruleset again at once. Running `.github/scripts/apply_settings.py` restores it. Then check that the `checks` workflow passes on the default branch. A repository without such a ruleset has nothing to disable.
4. **Release.** The commit of the merge is titled "Merge commit from fork", which does not follow the Conventional Commits format, so the `release` workflow cannot compute the version from it: start it with the version of the fix. Release a fixed version of each version that this file lists as supported. The fix of a maintained older version is not covered here.
5. **Disclose.** Publish the advisory with the fixed version, which deletes the temporary private fork. Request a CVE identifier if it is wanted. Credit the person who reported the fault if they wish: they must accept the credit before it is public.
6. **Learn.** Review how the report was handled, as [ADR 0012](docs/adr/0012-responding-to-an-incident.md) says.

A secret that has been exposed is revoked and replaced before anything else, and the history is cleaned afterwards if that still helps. A finding of the secret detection is an incident ([ADR 0012](docs/adr/0012-responding-to-an-incident.md)).

## Supported versions

Only the latest release receives fixes, as stated in the [README](README.md#versioning).
