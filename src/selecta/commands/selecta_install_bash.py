import os
import sys

already_there = False

command_tpl = r"""bind -x '"\C-[{r}":"\selecta --bash -y <(history)"'"""


def main():
    if sys.argv[1] == '-h' or sys.argv[1] == '--help':
        print('whee')

    print(command_tpl)
    sys.exit(0)

    # with open(os.path.join(os.path.expanduser("~"), '.bashrc'), 'r') as f:
    #     for line in f:
    #         if command in line:  # already installed
    #             already_there = True
    #             break

    # if not already_there:
    #     with open(os.path.join(os.path.expanduser("~"), '.bashrc'), 'a+') as f:
    #         # append hotkey binding to .bashrc
    #         f.write('\n{}\n'.format(command))


if __name__ == '__main__':
    main()
