# selecta
## Interactively select an entry from your history.

```
$ selecta <(history)
```

# Installation

create a symlink:

```
$ sudo ln -s selecta.py /usr/bin/selecta
```

Add this to your .bashrc to bind the command to your ALTGR+e key:

```
bind '"\C-[e":"\C-a\C-kselecta <(history)\C-m"'
```
