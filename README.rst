selecta - Interactively select an entry from your bash/zsh history.
-------------------------------------------------------------------

This is a python clone of François Fleuret's excellent `selector
<http://www.idiap.ch/~fleuret/software.html#selector/>`_

Usage
-----

::

    $ selecta.py --bash -y <(history)

Keys
----

CTRL+i: toggle case sensitivity

CTRL+r: toggle REGEX search

Installation
------------

create a symlink:

::

    $ sudo ln -s selecta.py /usr/bin/selecta

Add this to your .bashrc to bind the command to ALT+e:

::

    bind '"\C-[e":"\C-a\C-kselecta <(history)\C-m"'


.. code-block::

    usage: selecta [-h] [-i] [-b] [-z] [-e] [-a] [-d] [-y] [--bash] [--zsh]
                   [infile]

    positional arguments:
      infile

    optional arguments:
      -h, --help            show this help message and exit
      -i, --revert-order
      -b, --remove-bash-prefix
      -z, --remove-zsh-prefix
      -e, --regexp
      -a, --case-sensitive
      -d, --remove-duplicates
      -y, --show-hits
      --bash
      --zsh
