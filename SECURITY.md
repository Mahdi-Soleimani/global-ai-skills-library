# Security policy

Downloaded Skill content is untrusted input. The project does not execute downloaded code during collection or static scanning.

- Never place secrets, credentials, private research originals, or security evidence in public issues or pull requests.
- Report suspected vulnerabilities without exploit payloads or live-target data.
- Dynamic validation requires an OS-enforced sandbox with no external network, an empty allowlisted environment, read-only target files, bounded scratch output, and resource/time limits. If those controls are unavailable, do not execute the target code; record `needs_validation`.
- A clean static scan is not a security approval. Installation and execution require separate explicit gates.
