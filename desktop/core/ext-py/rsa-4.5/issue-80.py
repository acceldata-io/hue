#!/usr/bin/env python -bb

import rsa


with open('privkey.pem') as privatefile:
    keydata = privatefile.read()
pubkey = rsa.PrivateKey.load_pkcs1(keydata)
