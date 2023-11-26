import argparse
import os
import string

command_tpl = r'bindkey -s "^[{key}" "selecta --zsh -y <(history)^M"'


def main():
    already_there = False
    parser = argparse.ArgumentParser()
    parser.add_argument('key', type=str, choices=list(string.ascii_lowercase), help='Key for the zsh hotkey binding')
    args = parser.parse_args()

    command = command_tpl.format(key=args.key)

    with open(os.path.join(os.path.expanduser("~"), '.zshrc'), 'r') as f:
        for line in f:
            if command in line:  # already installed
                already_there = True
                print('keybinding already installed in .zshrc')
                break

    if not already_there:
        with open(os.path.join(os.path.expanduser("~"), '.zshrc'), 'a+') as f:
            # append hotkey binding to .zshrc
            f.write('\n{}\n'.format(command))
            print('keybinding has been appended to .zshrc')


if __name__ == '__main__':
    main()