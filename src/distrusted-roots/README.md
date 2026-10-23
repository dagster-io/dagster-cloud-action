# Distrusted roots

Root certificates that the images built from `src/Dockerfile` and
`src/Dockerfile.dagster-manylinux-builder` must not trust. Both images are
based on manylinux (AlmaLinux 8), which has not shipped a `ca-certificates`
update for the October 2026 eMudhra/emSign intermediate CA compromise
(https://emudhra.we-have-a-problem.com/), so the Dockerfiles copy these into
`/etc/pki/ca-trust/source/blacklist/` (EL8's name for the trust blocklist) and
run `update-ca-trust`, which is the RHEL-family equivalent of what Debian's
patched package does.

| File | Subject | SHA-256 |
|---|---|---|
| `emSign_ECC_Root_CA_-_G3.pem` | emSign ECC Root CA - G3 (eMudhra) | 86A1ECBA089C4A8D3BBE2734C612BA341D813E043CF9E8A862CD5C57A36BBE6B |
| `Comodo_AAA_Services_root.pem` | AAA Certificate Services (Sectigo, cross-signer) | D7A7A0FB5D7E2731D771E9484EBCDEF71D5F0C3E0A2948782BC83EE0EA699EF4 |

Remove this directory and the corresponding Dockerfile steps once the
manylinux base image carries an AlmaLinux `ca-certificates` that drops these
roots.
