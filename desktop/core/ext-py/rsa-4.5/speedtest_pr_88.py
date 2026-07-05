#!/usr/bin/env python3

import secrets
import math
import timeit


def bit_size(number):
    return number.bit_length()


def via_math_module(number):
    return int(math.ceil(bit_size(number) / 8.0))


def via_divmod(number):
    quanta, mod = divmod(bit_size(number), 8)

    if mod:
         quanta += 1
    return quanta


number = int.from_bytes(secrets.token_bytes(2048), 'little')
