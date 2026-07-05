#!/usr/bin/env python3

import rsa
from rsa import PrivateKey

privateKeyPem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAs1EKK81M5kTFtZSuUFnhKy8FS2WNXaWVmi/fGHG4CLw98+Yo\n0nkuUarVwSS0O9pFPcpc3kvPKOe9Tv+6DLS3Qru21aATy2PRqjqJ4CYn71OYtSwM\n/ZfSCKvrjXybzgu+sBmobdtYm+sppbdL+GEHXGd8gdQw8DDCZSR6+dPJFAzLZTCd\nB+Ctwe/RXPF+ewVdfaOGjkZIzDoYDw7n+OHnsYCYozkbTOcWHpjVevipR+IBpGPi\n1rvKgFnlcG6d/tj0hWRl/6cS7RqhjoiNEtxqoJzpXs/Kg8xbCxXbCchkf11STA8u\ndiCjQWuWI8rcDwl69XMmHJjIQAqhKvOOQ8rYTQIDAQABAoIBABpQLQ7qbHtp4h1Y\nORAfcFRW7Q74UvtH/iEHH1TF8zyM6wZsYtcn4y0mxYE3Mp+J0xlTJbeVJkwZXYVH\nL3UH29CWHSlR+TWiazTwrCTRVJDhEoqbcTiRW8fb+o/jljVxMcVDrpyYUHNo2c6w\njBxhmKPtp66hhaDpds1Cwi0A8APZ8Z2W6kya/L/hRBzMgCz7Bon1nYBMak5PQEwV\nF0dF7Wy4vIjvCzO6DSqA415DvJDzUAUucgFudbANNXo4HJwNRnBpymYIh8mHdmNJ\n/MQ0YLSqUWvOB57dh7oWQwe3UsJ37ZUorTugvxh3NJ7Tt5ZqbCQBEECb9ND63gxo\n/a3YR/0CgYEA7BJc834xCi/0YmO5suBinWOQAF7IiRPU+3G9TdhWEkSYquupg9e6\nK9lC5k0iP+t6I69NYF7+6mvXDTmv6Z01o6oV50oXaHeAk74O3UqNCbLe9tybZ/+F\ndkYlwuGSNttMQBzjCiVy0+y0+Wm3rRnFIsAtd0RlZ24aN3bFTWJINIsCgYEAwnQq\nvNmJe9SwtnH5c/yCqPhKv1cF/4jdQZSGI6/p3KYNxlQzkHZ/6uvrU5V27ov6YbX8\nvKlKfO91oJFQxUD6lpTdgAStI3GMiJBJIZNpyZ9EWNSvwUj28H34cySpbZz3s4Xd\nhiJBShgy+fKURvBQwtWmQHZJ3EGrcOI7PcwiyYcCgYEAlql5jSUCY0ALtidzQogW\nJ+B87N+RGHsBuJ/0cxQYinwg+ySAAVbSyF1WZujfbO/5+YBN362A/1dn3lbswCnH\nK/bHF9+fZNqvwprPnceQj5oK1n4g6JSZNsy6GNAhosT+uwQ0misgR8SQE4W25dDG\nkdEYsz+BgCsyrCcu8J5C+tUCgYAFVPQbC4f2ikVyKzvgz0qx4WUDTBqRACq48p6e\n+eLatv7nskVbr7QgN+nS9+Uz80ihR0Ev1yCAvnwmM/XYAskcOea87OPmdeWZlQM8\nVXNwINrZ6LMNBLgorfuTBK1UoRo1pPUHCYdqxbEYI2unak18mikd2WB7Fp3h0YI4\nVpGZnwKBgBxkAYnZv+jGI4MyEKdsQgxvROXXYOJZkWzsKuKxVkVpYP2V4nR2YMOJ\nViJQ8FUEnPq35cMDlUk4SnoqrrHIJNOvcJSCqM+bWHAioAsfByLbUPM8sm3CDdIk\nXVJl32HuKYPJOMIWfc7hIfxLRHnCN+coz2M6tgqMDs0E/OfjuqVZ\n-----END RSA PRIVATE KEY-----"
private_key = PrivateKey.load_pkcs1(privateKeyPem, format='PEM')

original_ct = "4501b4d669e01b9ef2dc800aa1b06d49196f5a09fe8fbcd037323c60eaf027bfb98432be4e4a26c567ffec718bcbea977dd26812fa071c33808b4d5ebb742d9879806094b6fbeea63d25ea3141733b60e31c6912106e1b758a7fe0014f075193faa8b4622bfd5d3013f0a32190a95de61a3604711bc62945f95a6522bd4dfed0a994ef185b28c281f7b5e4c8ed41176d12d9fc1b837e6a0111d0132d08a6d6f0580de0c9eed8ed105531799482d1e466c68c23b0c222af7fc12ac279bc4ff57e7b4586d209371b38c4c1035edd418dc5f960441cb21ea2bedbfea86de0d7861e81021b650a1de51002c315f1e7c12debe4dcebf790caaa54a2f26b149cf9e77d"
pt = bytes.fromhex("54657374")

print('----------------------------------------------')
print("Test with original ciphertext:")
ct = bytes.fromhex(f"{original_ct}")
try:
    message = rsa.decrypt(ct, private_key)
except:
    print("[*] \033[91mInvalid decryption\033[0m")
else:
    print("[!] \033[92mNo errors in decryption\033[0m")
    print("message == pt?", message == pt)

print('----------------------------------------------')
print("Test with prepended bytes to ciphertext:")
ct_with_prepend = bytes.fromhex(f"0000{original_ct}")
assert ct != ct_with_prepend
try:
    message = rsa.decrypt(ct_with_prepend, private_key)
except:
    print("\033[92m[*] Invalid decryption\033[0m")
else:
    print("\033[91m[!] No errors in decryption\033[0m")
    print("message == pt?", message == pt)

print('----------------------------------------------')
print("Test with appended bytes to ciphertext:")
ct_with_append = bytes.fromhex(f"{original_ct}0000")
assert ct != ct_with_append
try:
    message = rsa.decrypt(ct_with_append, private_key)
except:
    print("\033[92m[*] Invalid decryption\033[0m")
else:
    print("\033[91m[!] No errors in decryption\033[0m")
    print("message == pt?", message == pt)
