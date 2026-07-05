#!/usr/bin/env python3

from collections import Counter
from pprint import pprint

from rsa.randnum import randint

counter = Counter(randint(1024) for _ in range(1000000))

def by_occurrence(item):
    return item[1], item[0]

sorted_by_occurrence = sorted(counter.items(), key=by_occurrence)

print('Number  Occurrence')
for number, occurrence in sorted_by_occurrence[:5]:
    print(f'{number:4d}   {occurrence}')
print("…")
for number, occurrence in sorted_by_occurrence[-5:]:
    print(f'{number:4d}   {occurrence}')
