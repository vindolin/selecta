import argparse
import os
import string

# Shell wrapper functions that capture selecta's --print output
# and use shell-native mechanisms to place the command on the prompt.
# These replace the old TIOCSTI-based approach.

BASH_WRAPPER = r'''
# selecta shell integration (TIOCSTI-free)
selecta_insert() {
  local result
  result=$(selecta -b -y -p <(history))
  if [[ -n "$result" ]]; then
    READLINE_LINE="${result}${READLINE_LINE}"
    READLINE_POINT=${#result}
  fi
}
'''

ZSH_WRAPPER = r'''
# selecta shell integration (TIOCSTI-free)
selecta_insert() {
  local result
  result=$(selecta -z -y -p <(history 0))
  if [[ -n "$result" ]]; then
    LBUFFER="${result}${LBUFFER}"
  fi
}
'''

FISH_WRAPPER = r'''
# selecta shell integration (TIOCSTI-free)
function selecta_insert
  set -l result (PYTHON_GIL=1 selecta -z -y -p (history | cut -d " " -f 1 --complement | psub))
  if test -n "$result"
    commandline -r "$result"(commandline)
  end
end
'''

BASH_BIND = r'''bind -x '"\C-[{key}": selecta_insert' '''

ZSH_BIND = r'''zle -N selecta_insert
bindkey '^[{key}' selecta_insert'''

FISH_BIND = r'''bind \e{key} selecta_insert'''

SHELL_CONFIG = {
    'bash': {
        'wrapper': BASH_WRAPPER,
        'bind': BASH_BIND,
        'rcfile': '.bashrc',
    },
    'zsh': {
        'wrapper': ZSH_WRAPPER,
        'bind': ZSH_BIND,
        'rcfile': '.zshrc',
    },
    'fish': {
        'wrapper': FISH_WRAPPER,
        'bind': FISH_BIND,
        'rcfile': '.config/fish/config.fish',
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('key', type=str, choices=list(string.ascii_lowercase),
                        help='Key for the Alt+key hotkey binding')
    parser.add_argument('-p', '--print', dest='print_only', action='store_true',
                        default=False,
                        help='Print the shell configuration instead of writing to rc file')
    args = parser.parse_args()

    def detect_shell() -> str:
        """Detect the current shell from the SHELL environment variable."""
        shell_path = os.environ.get('SHELL', '')
        for name in ('fish', 'bash', 'zsh'):
            if name in shell_path:
                return name
        return 'bash'  # fallback

    shell = detect_shell()

    if shell not in SHELL_CONFIG:
        exit(f'Unsupported shell: {shell}')

    config = SHELL_CONFIG[shell]
    wrapper = config['wrapper'].strip()
    bind_cmd = config['bind'].format(key=args.key)
    rcfile = os.path.join(os.path.expanduser('~'), config['rcfile'])
    marker = '# selecta shell integration'

    if args.print_only:
        print(f'\n{marker}')
        print(wrapper)
        print(bind_cmd)
        return

    # Check if already installed
    already_there = False
    try:
        with open(rcfile, 'r') as f:
            if marker in f.read():
                already_there = True
    except FileNotFoundError:
        pass

    if already_there:
        print(f'selecta keybinding already installed in {rcfile}')
        print('To reinstall, remove the "# selecta shell integration" block from your rc file.')
    else:
        with open(rcfile, 'a') as f:
            f.write(f'\n{marker}\n{wrapper}\n{bind_cmd}\n')

        print(f'selecta keybinding (Alt+{args.key}) has been added to {rcfile}')
        print()
        print('To activate it in your current shell, run:')
        print()
        print(f'  source {rcfile}')
        print()
        print('Or simply open a new terminal.')


if __name__ == '__main__':
    main()
