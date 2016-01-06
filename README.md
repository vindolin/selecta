# selecta
## Interactively select an entry from your bash history.

This is a python clone of François Fleuret's brilliant [selector](http://www.idiap.ch/~fleuret/software.html#selector) utility.

```
$ selecta <(history)
```

## Keys

CTRL+i: toggle case sensitivity

CTRL+r: toggle REGEX search

## Installation

create a symlink:

```
$ sudo ln -s selecta.py /usr/bin/selecta
```

Add this to your .bashrc to bind the command to ALT+e:

```
bind '"\C-[e":"\C-a\C-kselecta <(history)\C-m"'
```
