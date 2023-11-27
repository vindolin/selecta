import argparse
import os
import string
import subprocess

command_tpl = r"""# selecta keybinding{n}bind -x '"\C-[{key}":"\selecta --bash -y <(history)"'"""


def main():
    already_there = False
    parser = argparse.ArgumentParser()
    parser.add_argument('key', type=str, choices=list(string.ascii_lowercase), help='Key for the bash hotkey binding')
    args = parser.parse_args()

    command = command_tpl.format(n='\n', key=args.key)

    with open(os.path.join(os.path.expanduser("~"), '.bashrc'), 'r') as f:
        for line in f:
            if command in line:  # already installed
                already_there = True
                print('keybinding already installed in .bashrc')
                break

    if not already_there:
        with open(os.path.join(os.path.expanduser("~"), '.bashrc'), 'a+') as f:
            # append hotkey binding to .bashrc
            f.write(f'\n{command}\n')
            subprocess.call(command, shell=True)
            print('keybinding has been appended to .bashrc')


if __name__ == '__main__':
    main()
