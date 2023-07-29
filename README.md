# DNS Resolver

A toy implementation of a DNS resolver. A DNS resolver resolves a domain name to an IP address. 

## Prerequisites
- Python >= 3.8

## Usage
```sh
$ python3 resolve.py <domain>
```

```sh
Usage: python3 resolve.py <domain>

Commands:
  resolve.py <domain>               Retrieves the IP address for a given domain.
```

### Example

```sh
$ python3 resolve.py google.com
  Querying 198.41.0.4 for google.com
  Querying 192.12.94.30 for google.com
  Querying 216.239.34.10 for google.com
  142.250.65.238
```

## References
https://implement-dns.wizardzines.com