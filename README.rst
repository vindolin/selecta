selecta - Interactively select an entry from your bash/zsh history.
-------------------------------------------------------------------

This is a python3 clone of François Fleuret's excellent `selector
<http://www.idiap.ch/~fleuret/software.html#selector/>`_ tool.

.. image:: https://raw.githubusercontent.com/vindolin/selecta/master/screencast.gif
   :width: 749
   :alt: Screencast
   :target: https://raw.githubusercontent.com/vindolin/selecta/master/screencast.gif


Usage
-----

::

    $ selecta --bash -y <(history)

Keys
----

CTRL+i: toggle case sensitivity

CTRL+r: toggle REGEX search

Installation
------------

::

    $ sudo pip3 install selecta

Add this to your .bashrc to bind the command to ALT+e:

::

    bind '"\C-[e":"\C-a\C-kselecta --bash -y <(history)\C-m"'


--help output
-------------

.. code-block::

    usage: selecta [-h] [-i] [-b] [-z] [-e] [-a] [-d] [-y] [--bash] [--zsh]
                   [infile]

    positional arguments:
      infile                the file which lines you want to select eg. <(history)

    optional arguments:
      -h, --help            show this help message and exit
      -i, --revert-order    revert the order of the lines
      -b, --remove-bash-prefix
                            remove the numeric prefix from bash history
      -z, --remove-zsh-prefix
                            remove the time prefix from zsh history
      -e, --regexp          start in regexp mode
      -a, --case-sensitive  start in case-sensitive mode
      -d, --remove-duplicates
                            remove duplicated lines
      -y, --show-hits       highlight the part of each line which match the
                            substrings or regexp
      --bash                standard for bash history search, same as -b -i -d
      --zsh                 standard for zsh history search, same as -b -i -d
