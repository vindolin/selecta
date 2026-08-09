selecta - Interactively search and select entries from your bash/zsh history.
-----------------------------------------------------------------------------

[![Python package](https://github.com/vindolin/selecta/actions/workflows/python-package.yml/badge.svg?branch=master)](https://github.com/vindolin/selecta/actions/workflows/python-package.yml)

This is a Python3 clone of François Fleuret's excellent [selector](https://fleuret.org/cgi-bin/gitweb/gitweb.cgi?p=selector.git;a=summary) tool.

[![Screencast](https://raw.githubusercontent.com/vindolin/selecta/master/screencast.gif)](https://raw.githubusercontent.com/vindolin/selecta/master/screencast.gif)


Usage
=====
Just type some characters and see which entries match your words.

You can search for whole sentences by prefixing your search with a double quote.

Use <kbd>up</kbd> and <kbd>down</kbd> arrows to navigate the list.

<kbd>Escape</kbd>/<kbd>Backspace</kbd> on the result list returns to the search input.

<kbd>Escape</kbd> on the search input closes selecta.

Press <kbd>Enter</kbd> to copy the selected entry to the console.

<kbd>CTRL+a</kbd> toggles case sensitivity

<kbd>CTRL+r</kbd> toggles regex search

Installation
============

```console
pip install selecta
```

Install the keyboard shortcut Alt+{key}:

```console
selecta_add_keybinding {the alt key you want to use}
```

This appends a shell wrapper function and keybinding to your `~/.bashrc` or `~/.zshrc`.

**How it works (TIOCSTI-free)**: Instead of using the legacy `TIOCSTI` ioctl (disabled on Linux 6.2+),
selecta now uses the same approach as `fzf`: the TUI draws to `/dev/tty`, and the selected command
is printed to stdout. A shell wrapper function captures this output and uses shell-native readline
commands to place the text on your prompt.

### Manual shell setup

If you prefer to set up the integration manually, add the following to your rc file:

**Bash** (`~/.bashrc`):

```bash
# selecta shell integration (TIOCSTI-free)
selecta_insert() {
  local result
  result=$(selecta -b -y -p <(history))
  if [[ -n "$result" ]]; then
    READLINE_LINE="${result}${READLINE_LINE}"
    READLINE_POINT=${#result}
  fi
}
bind -x '"\C-[s": selecta_insert'
```

**Zsh** (`~/.zshrc`):

```zsh
# selecta shell integration (TIOCSTI-free)
selecta_insert() {
  local result
  result=$(selecta -z -y -p <(history 0))
  if [[ -n "$result" ]]; then
    LBUFFER="${result}${LBUFFER}"
  fi
}
zle -N selecta_insert
bindkey '^[s' selecta_insert
```

**Fish** (`~/.config/fish/config.fish`):

```fish
# selecta shell integration (TIOCSTI-free)
function selecta_insert
  set -l result (PYTHON_GIL=1 selecta -z -y -p (history | cut -d " " -f 1 --complement | psub))
  if test -n "$result"
    commandline -r "$result"(commandline)
  end
end
bind \es selecta_insert
```

Replace `s` with your preferred key. After adding, run `source ~/.bashrc` (or `source ~/.zshrc`,
or `source ~/.config/fish/config.fish`) or open a new terminal.

### Legacy TIOCSTI mode

If you're on an older kernel and prefer the old behavior, selecta still supports TIOCSTI
as a fallback (just omit the `-p` flag). To re-enable TIOCSTI on Linux < 6.2:

```console
sudo sysctl -w dev.tty.legacy_tiocsti=1
```

Upgrade from older version to 0.2.x
-----------------------------------
Delete your old keybinding from .bashrc/.zshrc/config.fish and register the new version with:
```console
selecta_add_keybinding {key}
```


--help output
-------------

```
    usage: selecta [-h] [-i] [-b] [-z] [-r] [-a] [-d] [-y] [-p] [infile]

    positional arguments:
      infile                the file which lines you want to select eg. <(history)

    optional arguments:
      -h, --help            show this help message and exit
      -i, --reverse-order   reverse the order of the lines
      -b, --remove-bash-prefix
                            remove the numeric prefix from bash history
      -z, --remove-zsh-prefix
                            remove the time prefix from zsh history
      -r, --regexp          start in regexp mode
      -a, --case-sensitive  start in case-sensitive mode
      -d, --remove-duplicates
                            remove duplicated lines
      -y, --highlight-matches
                            highlight the part of each line which matches the
                            substrings or regexp
      -p, --print           print the selected command to stdout
                            (use with shell wrapper for TIOCSTI-free operation)
      -v, --version         print selecta version
```
