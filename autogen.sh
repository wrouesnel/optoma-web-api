#!/bin/bash
# See: https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
# Note: you can't refactor this out: its at the top of every script so the scripts can find their includes.
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
cd "${SCRIPT_DIR}" || exit 1  # This is an unlikely failure, so don't worry too much.

# Source common includes
source include.sh

# Check setup requirements
requires=(
    "git"
)

check_requirements "${requires[@]}"

log "Ensure pull request rebase."
# Note: will break for git < 1.7.9 (looking at you Centos 7 users)
log "Setup pull request rebasing"
if ! git config pull.rebase true ; then
    fatal 1 "Failed to setup git pull request rebease."
fi

# Note: will break for git < 2.23.0
log "Setup the blame file"
if ! git config blame.ignoreRevsFile .git-blame-ignore-revs ; then
    fatal 1 "Failed to setup git blame ignore revisions file."
fi

log "Ensure pull-request checkout for github is active."
if ! git config --get remote.origin.fetch "\+refs/pull/\*/head:refs/remotes/origin/pr/\*" ; then
    log "Setting up automatic fetch of pull requests"
    if ! git config --add remote.origin.fetch "+refs/pull/*/head:refs/remotes/origin/pr/*" ; then
        fatal 1 "Failed to configure pull request fetch for origin."
    fi
fi

log "Linking hook scripts"
repo_hooks_dir=".githooks"
git_hooks_dir=".git/hooks"
for hookname in \
  "applypatch-msg" \
  "commit-msg" \
  "post-update" \
  "pre-applypatch" \
  "pre-commit" \
  "pre-push" \
  "pre-rebase" \
  "prepare-commit-msg" \
  "update"; do
  # If we have a hook dir, then link a part runner into the corresponding script.
  if [ -e "${repo_hooks_dir}/${hookname}" ]; then
    log "Linking repository ${hookname} hook"
    if ! ln -sf "$(readlink -f ${repo_hooks_dir}/${hookname})" "${git_hooks_dir}/${hookname}"; then
      fatal 1 "Error linking hook script: ${repo_hooks_dir}/${hookname})" -> "${git_hooks_dir}/${hookname}"
    fi
  fi
done

if [ "$(readlink -f .git/hooks)" != "$(readlink -f .githooks)" ] ; then
    if ! ln -sf "$(readlink -f .githooks)" ".git/hooks"; then
        fatal 1 "Failed to activate repository git hooks."
    fi
fi

autogen_dir=".autogen.d"
while read -r autogen_script; do
    if ! "$autogen_script"; then
        fatal 1 "$autogen_script failed."
    fi
done < <(find "${autogen_dir}" -mindepth 1 -maxdepth 1 -type f -name '*.sh' | sort)

log "Success."
exit 0
