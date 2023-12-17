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
Install the keyboard shortcut ALT+{key}:

```console
selecta_add_keybinding {the alt key you want to use}
```

This will append one of the following lines to your ~/.bashrc/zshrc:

```console
bind -x '"\C-[{key}":"\selecta --bash -y <(history)"'
bindkey -s "^[{key}" "selecta --zsh -y <(history)^M"
```

Upgrade from older version to 0.2.x
-----------------------------------
Delete your old keybinding from .bashrc/.zshrc and register the new version with:
```console
selecta_add_keybinding
```


--help output
-------------

```
    usage: selecta [-h] [-i] [-b] [-z] [-e] [-a] [-d] [-y] [--bash] [--zsh]
                   [infile]

    positional arguments:
      infile                the file which lines you want to select eg. <(history)

    optional arguments:
      -h, --help            show this help message and exit
      -i, --reverse-order   reverse the order of the lines
      -b, --remove-bash-prefix
                            remove the numeric prefix from bash history
      -z, --remove-zsh-prefix
                            remove the time prefix from zsh history
      -e, --regexp          start in regexp mode
      -a, --case-sensitive  start in case-sensitive mode
      -d, --remove-duplicates
                            remove duplicated lines
      -y, --show-matches    highlight the part of each line which matches the
                            substrings or regexp
      --bash                standard for bash history search, same as -b -i -d
      --zsh                 standard for zsh history search, same as -b -i -d
```
