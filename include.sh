#!/bin/bash
# Common bash functions shared by the build scripts.

export bin_dir=".bin"
export autogen_dir=".autogen.d"
export githooks_dir=".githooks"
export scripts_dir=".scripts"

if command -v poetry 2>&1 1>/dev/null; then
    if ! export venv_dir="$(poetry env info --path)"; then
        export venv_dir=".venv"
    fi
else
    export venv_dir=".venv"
fi

# Color initialization guard due to the use of read-only bash variables.
export _colors_initialized=0
function _do_color_setup() {
    # Bash color includes from
    # https://raw.githubusercontent.com/WolfSoftware/bash-colour-include/master/src/bash-colour-include.sh

    fgBlack=''
    fgRed=''
    fgGreen=''
    fgYellow=''
    fgBlue=''
    fgMagenta=''
    fgCyan=''
    fgWhite=''

    bgBlack=''
    bgRed=''
    bgGreen=''
    bgYellow=''
    bgBlue=''
    bgMagenta=''
    bgCyan=''
    bgWhite=''

    screen_width=''
    bold=''
    dim=''
    underline=''
    stop_underline=''
    reverse=''
    cinvis=''
    cnorm=''
    bell=''
    reset=''
    cls=''

    if test -t 1; then
        # see if it supports colors...
        ncolors=$(tput colors)

        if test -n "${ncolors}" && test "${ncolors}" -ge 8; then
            fgBlack=$(tput setaf 0)
            fgRed=$(tput setaf 1)
            fgGreen=$(tput setaf 2)
            fgYellow=$(tput setaf 3)
            fgBlue=$(tput setaf 4)
            fgMagenta=$(tput setaf 5)
            fgCyan=$(tput setaf 6)
            fgWhite=$(tput setaf 7)

            bgBlack=$(tput setab 0)
            bgRed=$(tput setab 1)
            bgGreen=$(tput setab 2)
            bgYellow=$(tput setab 3)
            bgBlue=$(tput setab 4)
            bgMagenta=$(tput setab 5)
            bgCyan=$(tput setab 6)
            bgWhite=$(tput setab 7)

            screen_width=$(tput cols)
            bold=$(tput bold)
            dim=$(tput dim)
            underline=$(tput smul)
            stop_underline=$(tput rmul)
            reverse=$(tput rev)
            cinvis=$(tput civis)
            cnorm=$(tput cnorm)
            bell=$(tput bel)
            reset=$(tput sgr0)
            cls=$(tput clear)
        fi
    fi

    declare -x -r fgBlack
    declare -x -r fgRed
    declare -x -r fgGreen
    declare -x -r fgYellow
    declare -x -r fgBlue
    declare -x -r fgMagenta
    declare -x -r fgCyan
    declare -x -r fgWhite

    declare -x -r bgBlack
    declare -x -r bgRed
    declare -x -r bgGreen
    declare -x -r bgYellow
    declare -x -r bgBlue
    declare -x -r bgMagenta
    declare -x -r bgCyan
    declare -x -r bgWhite

    declare -x -r screen_width
    declare -x -r bold
    declare -x -r dim
    declare -x -r underline
    declare -x -r stop_underline
    declare -x -r reverse
    declare -x -r cinvis
    declare -x -r cnorm
    declare -x -r bell
    declare -x -r reset
    declare -x -r cls

    _colors_initialized=1
}

if [ $_colors_initialized != 1 ]; then
    _do_color_setup
fi

# Begin our includes.

function log() {
    echo "$*" 1>&2
}

function warn() {
    log "${fgYellow}WARN: $*${reset}"
}

function error() {
    log "${fgRed}ERROR: $*${reset}"
}

function success() {
    log "${fgGreen}SUCCESS: $*${reset}"
    exit 0
}

function fatal() {
    local retcode="$1"
    shift
    log "${fgRed}FATAL: $*${reset}"
    exit "$retcode"
}

# check_requirements and alias the input list to the exact paths.
function check_requirements() {
    # Alias all commands to their full paths.
    local cmd
    for p in "$@" ; do
        # Assign
        cmd="$(command -v "${p}")"
        alias "$p=${cmd}"
        # Check the command works.
        if [ ! -x "${cmd}" ]; then
            fatal 1 "Could not find required program (please install it): $p ($cmd)"
        fi
    done
    return 0
}

function is_ci() {
    if [ -n "${CODEBUILD_BUILD_ID+}" ]; then
        # AWS Codebuild CI
        return 0
    fi

    if [ -n "${CI}" ]; then
        # Generic CI
        return 0
    fi

    return 1
}