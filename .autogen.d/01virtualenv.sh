# See: https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
# Note: you can't refactor this out: its at the top of every script so the scripts can find their includes.
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

source include.sh

requires=(
    "poetry"
    "pip"
)

check_requirements "${requires[@]}"

log "Checking for correct Python version"
python_shortversion=$(cat .python-version|cut -d '.' -f1,2)
if command -v pyenv >/dev/null ; then
    if ! pyenv which python >/dev/null 2>&1 && [ "${python_shortversion}" != "system" ]; then
        log "Attempting to install missing Python version"
        if ! pyenv install; then
            log "Failed to install missing Python version"
        fi
    fi
    python="$(pyenv which python 2>/dev/null)"
    if [ -z "${python}" ]; then
        python="$(pyenv which python3)"
    fi
else
    if command -v python${python_shortversion} >/dev/null; then
        python="$(command -v python${python_shortversion})"
    else
        log "Failed to find python${python_shortversion}."
        log "Consider installing pyenv to set it up."
        log "Proceeding anyway but things may not work properly."
        if command -v python3 ; then
            python="$(command -v python3)"
        else
            python="$(command -v python)"
        fi
    fi
fi

log "Using python executable: ${python}"

log "Setting poetry python version"
if ! poetry env use "${python}"; then
    fatal 1 "Poetry failed to set python version"
fi

index_url="$(pip config --global get global.index-url 2>/dev/null)"
if [ ! -z "$index_url" ]; then
    log "Alternate default source found - setting as default for Poetry"
    if ! poetry source add --priority=default public-pypi "$index_url" ; then
        fatal 1 "Failed to set alternate default source."
    fi
fi

log "Installing project dependencies in --no-root-mode"
if ! poetry install --no-root ; then
    fatal 1 "Poetry failed to install dependencies"
fi
