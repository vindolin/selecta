from thefuzz import fuzz
from sys import argv
# from thefuzz import process

search = argv[1]

# method = fuzz.token_sort_ratio
# method = fuzz.partial_ratio
# method = fuzz.ratio
method = fuzz.token_set_ratio


def compare(line1, line2):
    return method(search, line1) - method(search, line2)


with open("tests/data/test_history.txt", "r") as fh:
    lines = fh.readlines()

lines.sort(key=lambda x: compare(x, search), reverse=True)

print(f'search: {search}\n')

for line in lines[:50]:
    line = line.split(None, 1)[1].strip()
    print(line)
