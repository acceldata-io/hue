"""
"""

import timeit

setup = '''
import random

random.seed('slartibartfast')
numbers = [random.randint(0, 10) for _ in range(100)]
'''

if __name__ == '__main__':
    print('List time: ', timeit.timeit(
        '[number in [2, 3, 5, 7] for number in numbers]',
        setup=setup))

    print('Set time: ', timeit.timeit(
        '[number in {2, 3, 5, 7} for number in numbers]',
        setup=setup))

    print('Tuple time: ', timeit.timeit(
        '[number in (2, 3, 5, 7) for number in numbers]',
        setup=setup))

    print('Single construction: ', timeit.timeit(
        '[number in TRIVIAL_PRIMES for number in numbers]',
        setup=setup + 'TRIVIAL_PRIMES = {2, 3, 5, 7}'))
