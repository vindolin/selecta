import argparse
import os
import string

from selecta import inject_command

shells = {
    'bash': {'command_tpl': r"""bind -x '"\C-[{key}":"\selecta -b -y <(history)"'"""},
    'zsh': {'command_tpl': r'''bindkey -s "^[{key}" "selecta -z -y <(history 0)^M"'''},
}


def main():
    already_there = False
    parser = argparse.ArgumentParser()
    parser.add_argument('key', type=str, choices=list(string.ascii_lowercase), help='Key for the bash hotkey binding')
    args = parser.parse_args()

    shell = 'bash' if 'bash' in os.environ['SHELL'] else 'zsh'

    if shell not in shells:
        exit(f'Unsupported shell: {shell}')

    command = shells[shell]['command_tpl'].format(n='\n', key=args.key)

    with open(os.path.join(os.path.expanduser("~"), '.bashrc'), 'r') as f:
        for line in f:
            if command in line:  # already installed
                already_there = True
                print('keybinding already installed in .bashrc')
                break

    if not already_there:
        with open(os.path.join(os.path.expanduser("~"), '.bashrc'), 'a+') as f:
            # append hotkey binding to .bashrc
            f.write(f'\n# selecta keybinding\n{command}\n')
            inject_command(f' {command}\n')

            print('keybinding has been appended to .bashrc')


if __name__ == '__main__':
    main()
