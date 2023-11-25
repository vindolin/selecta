import os

command = r'bindkey -s "^[r"  "selecta --zsh -y <(history)^M"'

already_there = False

if __name__ == '__main__':
    with open(os.path.join(os.path.expanduser("~"), '.zshrc'), 'r') as f:
        for line in f:
            if command in line:  # already installed
                already_there = True
                break

    if not already_there:
        with open(os.path.join(os.path.expanduser("~"), '.zshrc'), 'a+') as f:
            # append hotkey binding to .zshrc
            f.write('\n{}\n'.format(command))
