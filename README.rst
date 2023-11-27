selecta - Interactively search and select entries from your bash/zsh history.
-----------------------------------------------------------------------------

This is a Python3 clone of François Fleuret's excellent `selector
<http://www.idiap.ch/~fleuret/software.html#selector/>`_ tool.

.. image:: https://raw.githubusercontent.com/vindolin/selecta/master/screencast.gif
   :width: 749
   :alt: Screencast
   :target: https://raw.githubusercontent.com/vindolin/selecta/master/screencast.gif


Usage
-------
You can search for whole sentences by prefixing your search with a double quote.


Hotkeys
-------

CTRL+a: toggle case sensitivity

CTRL+r: toggle REGEX search

Installation
------------

::

    $ pip install selecta

Install the keyboard shortcut ALT+{key}:

::

    $ selecta_add_keybinding {the alt key you want to use}

This will append one of the following lines to your ~/.bashrc/zshrc:

::

    bind -x '"\C-[{key}":"\selecta --bash -y <(history)"'
    bindkey -s "^[{key}" "selecta --zsh -y <(history)^M"


--help output
-------------

.. code-block::

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

TODO
----

* Add the cd feature from selector.
* Implement missing command line switches.
* Add missing keyboard shortcuts
