# WinDoesNot development rules

We maintain both the x86-64 ISO and the Asahi/ARM64 variant. For each fix,
explicitly decide its scope: **both**, **x86-64 only**, or **Asahi only**.
Record the decision, reason, affected source/build paths, validation per platform,
and remaining work in [docs/platform-fixes.md](docs/platform-fixes.md).
Use shared sources for shared behavior. Keep hardware-specific work conditional;
do not apply Asahi kernel, bootloader, or device assumptions to x86-64.
Do not equate a successful desktop test on one machine with testing either ISO.
Distinguish source changes, host deployment, built images, and live hardware tests.
When a session ends, update the ledger so work can resume without chat history.
